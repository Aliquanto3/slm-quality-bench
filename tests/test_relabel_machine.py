"""Commande ``relabel-machine`` : libellé public donné après coup à une campagne lancée sans
``$QUALITY_BENCH_MACHINE``. Campagnes synthétiques, sans Ollama, GPU ni réseau."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from slm_quality_bench.common import paths
from slm_quality_bench.common.canonical import sha256_hex
from slm_quality_bench.common.jsonl import read_jsonl, rewrite_jsonl
from slm_quality_bench.common.locks import FileLock
from slm_quality_bench.common.manifest import (
    ManifestMismatchError,
    blocking_hash,
    ensure_manifest,
    harness_hash,
)
from slm_quality_bench.common.schemas import validate
from slm_quality_bench.report import release

from .judge_fakes import CAMPAIGN as JUDGE_CAMPAIGN
from .judge_fakes import FakeServer, build_campaign
from .report_factories import CAMPAIGN, JUDGE_ID, make_campaign
from .test_release import _add_measures, _registry

OLD = "tour-rtx3050"  # libellé du manifeste synthétique, traité ici comme « à remplacer »
NEW = "banc-test"
TS = "2026-10-29T10:00:00Z"
BACKUP = ".avant-relabel"


@pytest.fixture(autouse=True)
def _reset_logging():
    yield
    from slm_quality_bench.common.logs import setup_logging

    setup_logging("test", None)


def _main(*argv: str) -> int:
    from slm_quality_bench.__main__ import main

    return main(["relabel-machine", *argv])


def _relabel(*extra: str, campaign: str = CAMPAIGN, label: str = NEW) -> int:
    return _main("--campaign", campaign, "--label", label, *extra)


def _judgment_dir() -> Path:
    return paths.judgment_dir(CAMPAIGN, JUDGE_ID)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _data() -> dict[str, bytes]:
    """Fichiers de la campagne, hors journal du relabel (écrit même en cas de refus)."""
    return {k: v for k, v in _tree(paths.campaign_dir(CAMPAIGN)).items() if k != "log-relabel.log"}


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    """Campagne complète : génération, correction, chauffes, mémoire, jugement (lignes et lot)."""
    synthetic = make_campaign(tmp_path, monkeypatch)
    _add_measures(synthetic)
    graded = [r for r in synthetic.grading if r["judgment_manifest"] is not None]
    assert graded
    judgment, keys = [], []
    for record in graded[:3]:
        key = f"{record['key']}|c1"
        keys.append(key)
        judgment.append(
            {
                "schema": "qb.judgment/1",
                "key": key,
                "generation_key": record["key"],
                "manifest": synthetic.judgment_hash,
                "criterion": "c1",
                "judge": JUDGE_ID,
                "verdict": True,
                "probability": 0.9,
                "tokens": {"input": 10, "output": 2},
                "cost_usd": 0.0,
                "attempts": 1,
                "error": None,
                "created_at": "2026-10-15T08:12:03Z",
            }
        )
    batch = {
        "schema": "qb.batch/1",
        "key": "batch-1|submitted",
        "batch_id": "b1",
        "judge": JUDGE_ID,
        "manifest": synthetic.judgment_hash,
        "created_at": "2026-10-15T08:12:03Z",
        "status": "submitted",
        "keys": keys,
        "estimate_usd": 0.1,
    }
    for line in (*judgment, batch):
        validate(line)
    rewrite_jsonl(paths.judgment_path(CAMPAIGN, JUDGE_ID), judgment)
    rewrite_jsonl(paths.batches_path(CAMPAIGN, JUDGE_ID), [batch])
    return synthetic


def _assert_coherent(label: str = NEW) -> tuple[str, str]:
    """Toutes les empreintes portées par les fichiers sont celles des manifestes courants."""
    manifest = _json(paths.generation_manifest_path(CAMPAIGN))
    judgment = _json(paths.judgment_manifest_path(CAMPAIGN, JUDGE_ID))
    validate(manifest)
    validate(judgment)
    generation_hash, judgment_hash = blocking_hash(manifest), blocking_hash(judgment)
    assert manifest["blocking"]["machine"] == label
    assert judgment["blocking"]["machine"] == label
    assert judgment["blocking"]["generation_manifest"] == generation_hash
    for path in (paths.generation_path(CAMPAIGN), paths.warmups_path(CAMPAIGN)):
        lines = read_jsonl(path)
        assert lines and {line["manifest"] for line in lines} == {generation_hash}
    assert {line["manifest"] for line in read_jsonl(paths.memory_path(CAMPAIGN))} == {
        generation_hash
    }
    for path in (
        paths.judgment_path(CAMPAIGN, JUDGE_ID),
        paths.batches_path(CAMPAIGN, JUDGE_ID),
    ):
        lines = read_jsonl(path)
        assert lines and {line["manifest"] for line in lines} == {judgment_hash}
    grading = read_jsonl(paths.grading_path(CAMPAIGN))
    assert {line["generation_manifest"] for line in grading} == {generation_hash}
    assert {line["judgment_manifest"] for line in grading} == {None, judgment_hash}
    return generation_hash, judgment_hash


def test_relabel_rewrites_every_file_coherently(campaign):
    before = _tree(paths.campaign_dir(CAMPAIGN))
    assert _relabel() == 0
    generation_hash, judgment_hash = _assert_coherent()
    assert (generation_hash, judgment_hash) != (campaign.generation_hash, campaign.judgment_hash)
    after = _tree(paths.campaign_dir(CAMPAIGN))
    rewritten = {
        "manifest.json",
        "generation.jsonl",
        "warmups.jsonl",
        "memory.jsonl",
        "grading.jsonl",
        f"judgment-{JUDGE_ID}/manifest.json",
        f"judgment-{JUDGE_ID}/judgment.jsonl",
        f"judgment-{JUDGE_ID}/batches.jsonl",
    }
    for name in rewritten:
        assert after[name] != before[name], name
        assert after[name + BACKUP] == before[name], name  # sauvegarde = original
    assert set(after) - set(before) == {n + BACKUP for n in rewritten} | {"log-relabel.log"}
    assert not any(name.endswith(".relabel.tmp") for name in after)
    # Les lignes ne changent que par l'empreinte : même nombre, mêmes autres champs.
    hashes = ("manifest", "generation_manifest", "judgment_manifest")
    for name in ("generation.jsonl", "grading.jsonl", f"judgment-{JUDGE_ID}/judgment.jsonl"):
        old_lines = [json.loads(x) for x in before[name].splitlines()]
        new_lines = [json.loads(x) for x in after[name].splitlines()]
        assert len(old_lines) == len(new_lines)
        for old_line, new_line in zip(old_lines, new_lines, strict=True):
            keep = {k: v for k, v in old_line.items() if k not in hashes}
            assert keep == {k: v for k, v in new_line.items() if k not in hashes}


def test_old_label_is_never_written_in_clear(campaign):
    assert _relabel() == 0
    root = paths.campaign_dir(CAMPAIGN)
    for path in root.rglob("*"):
        if path.is_file() and not path.name.endswith(BACKUP):
            text = path.read_text(encoding="utf-8")
            # Ni en clair ni haché : un nom d'hôte haché se retrouve par force brute.
            assert OLD not in text and sha256_hex(OLD) not in text, path.name
    manifest = _json(paths.generation_manifest_path(CAMPAIGN))
    relabels = manifest["informative"]["relabels"]
    assert relabels == [{"to": NEW, "at": relabels[0]["at"]}]
    judgment = _json(paths.judgment_manifest_path(CAMPAIGN, JUDGE_ID))
    assert judgment["informative"]["relabels"] == [{"to": NEW, "at": relabels[0]["at"]}]
    log = paths.log_path(CAMPAIGN, "relabel").read_text(encoding="utf-8")
    assert NEW in log and "[relabel]" in log


def test_dry_run_lists_files_and_writes_nothing(campaign, capsys):
    before = _tree(paths.campaign_dir(CAMPAIGN))
    assert _relabel("--dry-run") == 0
    assert _tree(paths.campaign_dir(CAMPAIGN)) == before
    text = capsys.readouterr().err
    n = len(campaign.generation)
    assert f"generation.jsonl à réécrire : {n} ligne(s)" in text
    assert "grading.jsonl" in text and "batches.jsonl" in text and "memory.jsonl" in text
    assert "rien écrit" in text and OLD not in text


def test_refuses_the_current_label(campaign):
    before = _data()
    assert _relabel(label=OLD) == 1
    assert _relabel(label=f"  {OLD} ") == 1
    assert _data() == before


def test_refuses_an_empty_label(campaign):
    assert _relabel(label="   ") == 2


@pytest.mark.parametrize("lock", ["generation", "judgment"])
def test_refuses_while_a_lock_is_held(campaign, lock):
    path = (
        paths.generation_lock_path(CAMPAIGN)
        if lock == "generation"
        else paths.judgment_lock_path(CAMPAIGN, JUDGE_ID)
    )
    path.touch()
    before = _data()
    with FileLock(path):
        assert _relabel() == 1
        assert _relabel("--dry-run") == 1
    assert _data() == before


def test_free_locks_do_not_block_and_are_released(campaign):
    paths.generation_lock_path(CAMPAIGN).touch()
    paths.judgment_lock_path(CAMPAIGN, JUDGE_ID).touch()
    assert _relabel() == 0
    with FileLock(paths.generation_lock_path(CAMPAIGN)):
        pass


def _corrupt(name: str, edit) -> None:
    path = paths.campaign_dir(CAMPAIGN) / name
    lines = read_jsonl(path)
    edit(lines)
    rewrite_jsonl(path, lines)


@pytest.mark.parametrize(
    "name, edit",
    [
        ("generation.jsonl", lambda lines: lines[3].update(manifest="0" * 64)),
        ("warmups.jsonl", lambda lines: lines[0].update(manifest="1" * 64)),
        ("memory.jsonl", lambda lines: lines[-1].update(manifest="2" * 64)),
        ("grading.jsonl", lambda lines: lines[2].update(generation_manifest="3" * 64)),
        (f"judgment-{JUDGE_ID}/judgment.jsonl", lambda lines: lines[1].update(manifest="4" * 64)),
        (f"judgment-{JUDGE_ID}/batches.jsonl", lambda lines: lines[0].update(manifest="5" * 64)),
    ],
)
def test_refuses_a_line_of_another_manifest_and_writes_nothing(campaign, name, edit):
    _corrupt(name, edit)
    before = _data()
    assert _relabel() == 1
    assert _data() == before


def test_refuses_a_grading_line_pointing_at_an_unknown_judgment(campaign):
    def edit(lines):
        line = next(x for x in lines if x["judgment_manifest"] is not None)
        line["judgment_manifest"] = "6" * 64

    _corrupt("grading.jsonl", edit)
    assert _relabel() == 1
    assert _json(paths.generation_manifest_path(CAMPAIGN))["blocking"]["machine"] == OLD


def test_refuses_an_interrupted_final_line(campaign):
    path = paths.generation_path(CAMPAIGN)
    path.write_bytes(path.read_bytes() + b'{"schema":"qb.gener')
    assert _relabel() == 1
    assert _json(paths.generation_manifest_path(CAMPAIGN))["blocking"]["machine"] == OLD


def test_refuses_judgment_lines_without_a_manifest(campaign):
    paths.judgment_manifest_path(CAMPAIGN, JUDGE_ID).unlink()
    assert _relabel() == 1


def test_refuses_when_a_backup_already_exists(campaign):
    backup = paths.generation_path(CAMPAIGN).with_name("generation.jsonl" + BACKUP)
    backup.write_bytes(b"ancien")
    assert _relabel() == 1
    assert backup.read_bytes() == b"ancien"
    assert _json(paths.generation_manifest_path(CAMPAIGN))["blocking"]["machine"] == OLD


def test_unknown_campaign_exits_1(campaign):
    assert _relabel(campaign="absente") == 1


def test_judgment_of_another_generation_is_left_alone(campaign):
    other = _json(paths.judgment_manifest_path(CAMPAIGN, JUDGE_ID))
    other["blocking"]["generation_manifest"] = "7" * 64
    directory = paths.judgment_dir(CAMPAIGN, "autre")
    directory.mkdir()
    path = paths.judgment_manifest_path(CAMPAIGN, "autre")
    other["blocking"]["judge"] = {**other["blocking"]["judge"], "id": "autre"}
    path.write_text(json.dumps(other), encoding="utf-8")
    before = path.read_bytes()
    assert _relabel() == 0
    assert path.read_bytes() == before
    _assert_coherent()


def test_failed_replacement_restores_the_files(campaign, monkeypatch):
    import os

    before = _data()
    real, calls = os.replace, []

    def flaky(src, dst):
        calls.append(dst)
        if len(calls) == 4:
            raise OSError("disque plein simulé")
        return real(src, dst)

    monkeypatch.setattr(os, "replace", flaky)
    assert _relabel() == 1
    monkeypatch.setattr(os, "replace", real)
    # Tout restauré : ni sauvegarde devenue inutile ni temporaire, relance possible.
    assert _data() == before
    assert "remis comme avant" in paths.log_path(CAMPAIGN, "relabel").read_text(encoding="utf-8")
    assert _relabel() == 0
    _assert_coherent()


def test_failed_restore_lists_the_files_and_keeps_their_backup(campaign, monkeypatch):
    """Sous Windows, la restauration peut échouer à son tour (fichier ouvert ailleurs) : le
    message nomme les fichiers non restaurés et leur sauvegarde, gardée."""
    import os

    from slm_quality_bench import relabel as module

    before = _data()
    real_replace, real_copy, calls = os.replace, module.shutil.copy2, []

    def flaky(src, dst):
        calls.append(dst)
        if len(calls) == 4:
            raise OSError("disque plein simulé")
        return real_replace(src, dst)

    def copy(src, dst, *args, **kwargs):
        if str(src).endswith(BACKUP) and Path(src).name.startswith("generation.jsonl"):
            raise PermissionError("fichier ouvert ailleurs")
        return real_copy(src, dst, *args, **kwargs)

    monkeypatch.setattr(os, "replace", flaky)
    monkeypatch.setattr(module.shutil, "copy2", copy)
    assert _relabel() == 1
    monkeypatch.setattr(os, "replace", real_replace)
    monkeypatch.setattr(module.shutil, "copy2", real_copy)
    after = _data()
    log = paths.log_path(CAMPAIGN, "relabel").read_text(encoding="utf-8")
    assert "1 fichier(s) NON restauré(s)" in log and f"generation.jsonl{BACKUP}" in log
    assert after["generation.jsonl"] != before["generation.jsonl"]  # resté réécrit
    assert after[f"generation.jsonl{BACKUP}"] == before["generation.jsonl"]
    assert after["manifest.json"] == before["manifest.json"]  # restauré
    assert {k for k in after if k.endswith(BACKUP)} == {f"generation.jsonl{BACKUP}"}
    assert not any(name.endswith(".relabel.tmp") for name in after)


def test_second_relabel_needs_the_backups_moved(campaign):
    assert _relabel() == 0
    assert _relabel(label="autre-libelle") == 1  # sauvegardes du premier relabel présentes
    for path in list(paths.campaign_dir(CAMPAIGN).rglob(f"*{BACKUP}")):
        path.unlink()
    assert _relabel(label="autre-libelle") == 0
    manifest = _json(paths.generation_manifest_path(CAMPAIGN))
    assert [r["to"] for r in manifest["informative"]["relabels"]] == [NEW, "autre-libelle"]
    assert all(set(r) == {"to", "at"} for r in manifest["informative"]["relabels"])
    _assert_coherent("autre-libelle")


# -- Les commandes suivantes acceptent la campagne ----------------------------------------------


def _next_run_manifest(label: str, harness: str | None = None) -> dict:
    """Manifeste qu'une reprise de ``generate`` construirait : mêmes jeu, modèles et version
    d'Ollama, libellé de l'environnement et empreinte ``harness`` du code qui reprend (par
    défaut, celle du lancement : hypothèse d'un code de harnais inchangé)."""
    manifest = _json(paths.generation_manifest_path(CAMPAIGN))
    manifest["blocking"]["machine"] = label
    if harness is not None:
        manifest["blocking"]["harness_hash"] = harness
    manifest["informative"]["python"] = "autre-version"  # l'informatif ne bloque jamais
    return manifest


def test_generate_resume_compares_the_new_label(campaign):
    """Reprise avec le même code de harnais qu'au lancement (seul cas où elle est possible)."""
    old = _json(paths.generation_manifest_path(CAMPAIGN))
    assert _relabel() == 0
    path = paths.generation_manifest_path(CAMPAIGN)
    existing = ensure_manifest(path, _next_run_manifest(NEW))
    assert blocking_hash(existing) == blocking_hash(_next_run_manifest(NEW))
    # Sans la variable d'environnement (ou avec l'ancien libellé), la reprise reste refusée.
    with pytest.raises(ManifestMismatchError) as error:
        ensure_manifest(path, _next_run_manifest(OLD))
    assert error.value.path == "blocking.machine"
    assert blocking_hash(old) != blocking_hash(existing)


def test_generate_resume_is_refused_once_the_harness_changed(campaign):
    """Le relabel ne contourne pas ``harness_hash`` : un code de harnais modifié depuis le
    lancement (comme celui qui ajoute cette commande, qui touche ``common/``) refuse la reprise,
    même avec le bon libellé."""
    assert _relabel() == 0
    current = harness_hash()
    assert _json(paths.generation_manifest_path(CAMPAIGN))["blocking"]["harness_hash"] != current
    with pytest.raises(ManifestMismatchError) as error:
        ensure_manifest(paths.generation_manifest_path(CAMPAIGN), _next_run_manifest(NEW, current))
    assert error.value.path == "blocking.harness_hash"


def test_report_accepts_the_relabeled_campaign(campaign):
    from slm_quality_bench.__main__ import main

    assert main(["report", "--campaign", CAMPAIGN]) == 0
    assert _relabel() == 0
    assert main(["report", "--campaign", CAMPAIGN]) == 0
    summary = _json(paths.campaign_exports_dir(CAMPAIGN) / "summary.json")
    assert summary["generation_manifest"] == blocking_hash(
        _json(paths.generation_manifest_path(CAMPAIGN))
    )
    manifest = _json(paths.campaign_exports_dir(CAMPAIGN) / "manifest.json")
    assert manifest["blocking"]["machine"] == NEW
    assert manifest["informative"]["relabels"] == [
        {"to": NEW, "at": manifest["informative"]["relabels"][0]["at"]}
    ]
    for path in paths.campaign_exports_dir(CAMPAIGN).rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert OLD not in text and sha256_hex(OLD) not in text, path.name


def test_export_release_accepts_the_relabeled_campaign(campaign, monkeypatch):
    # Avant : le libellé de la campagne n'est pas public (comme un nom d'hôte), export refusé.
    monkeypatch.setattr(release, "PUBLIC_MACHINES", {})
    with pytest.raises(release.ReleaseError, match="machine"):
        release.export_release([CAMPAIGN], "1.2.3", _registry())
    assert _relabel() == 0
    with pytest.raises(release.ReleaseError, match="machine"):
        release.export_release([CAMPAIGN], "1.2.3", _registry())
    monkeypatch.setitem(release.PUBLIC_MACHINES, NEW, {"gpu": "GPU test", "os": "OS test"})
    target = release.export_release([CAMPAIGN], "1.2.3", _registry())
    document = _json(target)
    assert {r["machine"] for r in document["results"]} == {NEW}
    assert OLD not in target.read_text(encoding="utf-8")
    assert document["campaigns"][0]["generation_hash"] == blocking_hash(
        _json(paths.generation_manifest_path(CAMPAIGN))
    )


def test_judge_resume_skips_judged_criteria_and_grade_accepts(monkeypatch, tmp_path):
    """Bout en bout avec le juge local simulé : jugement, correction, relabel, reprise du juge
    (aucun critère rejugé), nouvelle correction identique."""
    from slm_quality_bench.__main__ import main
    from slm_quality_bench.judge import commands

    server = FakeServer()
    monkeypatch.setattr(commands, "make_transport", server.transport)
    monkeypatch.setattr(commands, "SLEEP", lambda seconds: None)
    build_campaign()
    config_dir = tmp_path / "campaigns_yaml"
    config_dir.mkdir()
    from .judge_fakes import SET_ID

    (config_dir / f"{JUDGE_CAMPAIGN}.yaml").write_text(
        f"set: {SET_ID}\ngeneration:\n  models:\n"
        '    - {tag: "m:1b", family: qwen, tracks: [think_off], think_off: false, '
        "num_ctx_max: 32768}\ngrading:\n  judge: winnow\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(paths, "campaign_config_path", lambda c: config_dir / f"{c}.yaml")

    assert main(["judge", "--campaign", JUDGE_CAMPAIGN, "--judge", "winnow"]) == 0
    assert main(["grade", "--campaign", JUDGE_CAMPAIGN]) == 0
    requests = len(server.systemone_bodies())
    before = read_jsonl(paths.grading_path(JUDGE_CAMPAIGN))
    judged = read_jsonl(paths.judgment_path(JUDGE_CAMPAIGN, "winnow"))
    assert requests > 0 and judged

    assert _relabel(campaign=JUDGE_CAMPAIGN) == 0
    monkeypatch.setenv("QUALITY_BENCH_MACHINE", NEW)
    assert main(["judge", "--campaign", JUDGE_CAMPAIGN, "--judge", "winnow"]) == 0
    assert len(server.systemone_bodies()) == requests  # aucun critère rejugé
    assert len(read_jsonl(paths.judgment_path(JUDGE_CAMPAIGN, "winnow"))) == len(judged)
    assert main(["grade", "--campaign", JUDGE_CAMPAIGN]) == 0
    after = read_jsonl(paths.grading_path(JUDGE_CAMPAIGN))
    assert len(after) == len(before)
    assert [(r["key"], r["status"], r["score"]) for r in after] == [
        (r["key"], r["status"], r["score"]) for r in before
    ]
    manifest = _json(paths.generation_manifest_path(JUDGE_CAMPAIGN))
    assert {r["generation_manifest"] for r in after} == {blocking_hash(manifest)}
    judgment_manifest = _json(paths.judgment_manifest_path(JUDGE_CAMPAIGN, "winnow"))
    assert judgment_manifest["blocking"]["machine"] == NEW
    assert judgment_manifest["blocking"]["generation_manifest"] == blocking_hash(manifest)
