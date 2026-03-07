from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dfm_models import AnalysisSession, FeatureCandidate, OffenderRecord, OnshapeTarget
from onshape.auth import OnshapeCredentials, auth_config_summary, load_auth_config, save_auth_config
from onshape.export import _finalize_step_download
from onshape.feature_parser import parse_supported_features
from onshape.fs_eval import build_batch_feature_trace_script, extract_feature_fingerprints
from onshape.mapper import match_offenders_to_candidates
from onshape.remediation import build_proposals
from onshape_cli import _parse_onshape_url, _validate_target_is_partstudio
from onshape.session import load_session, save_session


class OnshapeWorkflowTests(unittest.TestCase):
    def test_parse_supported_features(self) -> None:
        payload = {
            "features": [
                {
                    "message": {
                        "featureType": "fillet",
                        "featureId": "filletA",
                        "name": "Fillet 1",
                        "parameters": [
                            {"message": {"parameterId": "radius", "expression": "0.5 mm", "name": "Radius"}}
                        ],
                    }
                },
                {
                    "message": {
                        "featureType": "extrude",
                        "featureId": "extrudeA",
                        "name": "Extrude 1",
                        "parameters": [
                            {"message": {"parameterId": "endBound", "value": "BLIND"}},
                            {"message": {"parameterId": "depth", "expression": "20 mm"}},
                        ],
                    }
                },
                {
                    "message": {
                        "featureType": "hole",
                        "featureId": "holeA",
                        "name": "Hole 1",
                        "parameters": [
                            {"message": {"parameterId": "diameter", "expression": "2.5 mm"}},
                            {"message": {"parameterId": "depth", "expression": "16 mm"}},
                        ],
                    }
                },
            ]
        }

        candidates = parse_supported_features(payload)

        self.assertEqual(len(candidates), 4)
        ids = {(row.feature_id, row.parameter_id) for row in candidates}
        self.assertIn(("filletA", "radius"), ids)
        self.assertIn(("extrudeA", "depth"), ids)
        self.assertIn(("holeA", "diameter"), ids)
        self.assertIn(("holeA", "depth"), ids)

    def test_mapping_and_proposals(self) -> None:
        offenders = [
            OffenderRecord(
                rule_id="R4",
                metric="Hole D/D Ratio",
                current_value=6.4,
                target_value=4.0,
                delta=2.4,
                occ_anchor={"centroid": {"x": 1.0, "y": 2.0, "z": 3.0}, "dominant_axis": "Z"},
                supported_remediations=["hole.depth", "hole.diameter"],
                meta={
                    "depth_mm": 16.0,
                    "diameter_mm": 2.5,
                    "target_depth_mm": 10.0,
                    "target_diameter_mm": 4.0,
                },
            )
        ]
        candidates = [
            FeatureCandidate(
                feature_id="holeA",
                feature_type="hole",
                parameter_path="parameters.depth.expression",
                current_expression="16 mm",
                editable=True,
                confidence=0.0,
                parameter_id="depth",
                meta={"numeric_value": 16.0},
            ),
            FeatureCandidate(
                feature_id="holeA",
                feature_type="hole",
                parameter_path="parameters.diameter.expression",
                current_expression="2.5 mm",
                editable=True,
                confidence=0.0,
                parameter_id="diameter",
                meta={"numeric_value": 2.5},
            ),
        ]

        matches = match_offenders_to_candidates(offenders, candidates, traces={"holeA": ["q1"]})
        proposals = build_proposals(offenders, matches)

        self.assertEqual(len(proposals), 2)
        actions = {row.action for row in proposals}
        self.assertEqual(actions, {"reduce_depth", "increase_diameter"})
        after_values = {row.after for row in proposals}
        self.assertIn("10 mm", after_values)
        self.assertIn("4 mm", after_values)

    def test_session_round_trip(self) -> None:
        session = AnalysisSession(
            session_id="abc123",
            target=OnshapeTarget(did="d1", wid="w1", eid="e1"),
            source_microversion="mv1",
            export_path="/tmp/example.step",
            offender_records=[],
            feature_candidates=[],
            proposals=[],
            audit_log=["created"],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("onshape.session.session_root", return_value=Path(tmpdir)):
                save_session(session)
                loaded = load_session("abc123")

        self.assertEqual(loaded.session_id, session.session_id)
        self.assertEqual(loaded.target.did, "d1")
        self.assertEqual(loaded.audit_log, ["created"])

    def test_auth_config_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            auth_path = Path(tmpdir) / "outside-repo" / "onshape_auth.json"
            with patch.dict(
                "os.environ",
                {
                    "ONSHAPE_AUTH_CONFIG_PATH": str(auth_path),
                    "ONSHAPE_ACCESS_KEY": "",
                    "ONSHAPE_SECRET_KEY": "",
                    "ONSHAPE_BASE_URL": "",
                    "ONSHAPE_AUTH_MODE": "",
                },
                clear=False,
            ):
                save_auth_config("ACCESS1234", "SECRET5678", "https://cad.onshape.com", "hmac")
                loaded = load_auth_config()
                summary = auth_config_summary()
                creds = OnshapeCredentials.from_env()

        self.assertEqual(loaded["access_key"], "ACCESS1234")
        self.assertEqual(loaded["secret_key"], "SECRET5678")
        self.assertEqual(summary["configured"], "yes")
        self.assertIn("...", summary["access_key_masked"])
        self.assertEqual(creds.access_key, "ACCESS1234")

    def test_repo_local_auth_config_is_rejected(self) -> None:
        bad_path = ROOT / "cache" / "bad_onshape_auth.json"
        with patch.dict("os.environ", {"ONSHAPE_AUTH_CONFIG_PATH": str(bad_path)}, clear=False):
            with self.assertRaises(RuntimeError):
                save_auth_config("A", "B", "https://cad.onshape.com", "hmac")

    def test_hmac_headers_match_documented_shape(self) -> None:
        creds = OnshapeCredentials(
            access_key="ACCESS",
            secret_key="SECRET",
            base_url="https://cad.onshape.com",
            auth_mode="hmac",
        )
        with patch("onshape.auth.secrets.token_hex", return_value="abc123"), patch(
            "onshape.auth.format_datetime", return_value="Sat, 07 Mar 2026 12:00:00 GMT"
        ):
            headers = creds.build_headers(
                "POST",
                "https://cad.onshape.com/api/v9/partstudios/d/did/w/wid/e/eid/export/step?configuration=default",
                body=b'{"storeInDocument":true}',
                content_type="application/json",
            )

        self.assertEqual(headers["Date"], "Sat, 07 Mar 2026 12:00:00 GMT")
        self.assertEqual(headers["On-Nonce"], "abc123")
        self.assertTrue(headers["Authorization"].startswith("On ACCESS:HmacSHA256:"))

    def test_parse_onshape_workspace_url(self) -> None:
        target = _parse_onshape_url(
            "https://cad.onshape.com/documents/479651ef821c32adc4e1f2b8/w/041fe92ea37cec17a3b5b910/e/fdeea4f7647555ed1fd73b0f"
        )
        self.assertEqual(target.did, "479651ef821c32adc4e1f2b8")
        self.assertEqual(target.wid, "041fe92ea37cec17a3b5b910")
        self.assertEqual(target.eid, "fdeea4f7647555ed1fd73b0f")

    def test_parse_non_workspace_url_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            _parse_onshape_url(
                "https://cad.onshape.com/documents/479651ef821c32adc4e1f2b8/v/041fe92ea37cec17a3b5b910/e/fdeea4f7647555ed1fd73b0f"
            )

    def test_assembly_target_is_rejected(self) -> None:
        class FakeClient:
            def get_elements(self, target):
                return [{"id": target.eid, "name": "Asm 1", "elementType": "ASSEMBLY"}]

        with self.assertRaises(RuntimeError):
            _validate_target_is_partstudio(
                FakeClient(), OnshapeTarget(did="d1", wid="w1", eid="e1")  # type: ignore[arg-type]
            )

    def test_multi_part_studio_is_rejected(self) -> None:
        class FakeClient:
            def get_elements(self, target):
                return [{"id": target.eid, "name": "Studio 1", "elementType": "PARTSTUDIO"}]

            def get_parts(self, target):
                return [{"name": "Part 1"}, {"name": "Part 2"}]

        with self.assertRaises(RuntimeError):
            _validate_target_is_partstudio(
                FakeClient(), OnshapeTarget(did="d1", wid="w1", eid="e1")  # type: ignore[arg-type]
            )

    def test_zip_export_is_unwrapped_to_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "part.step"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("R0-1axis.step", "ISO-10303-21;\nEND-ISO-10303-21;\n")
            extracted = _finalize_step_download(zip_path)
            contents = extracted.read_text()

        self.assertEqual(extracted.suffix, ".step")
        self.assertIn("ISO-10303-21", contents)

    def test_build_batch_feature_trace_script_mentions_feature_ids(self) -> None:
        candidates = [
            FeatureCandidate(
                feature_id="abc",
                feature_type="extrude",
                parameter_path="parameters.depth.expression",
                current_expression="25 mm",
                editable=True,
                confidence=0.0,
            ),
            FeatureCandidate(
                feature_id="def",
                feature_type="fillet",
                parameter_path="parameters.radius.expression",
                current_expression="4 mm",
                editable=True,
                confidence=0.0,
            ),
        ]

        script = build_batch_feature_trace_script(candidates)

        self.assertIn('fingerprint("abc", "extrude")', script)
        self.assertIn('fingerprint("def", "fillet")', script)
        self.assertIn("evBox3d", script)
        self.assertIn("evSurfaceDefinition", script)

    def test_extract_feature_fingerprints(self) -> None:
        payload = {
            "result": {
                "message": {
                    "features": [
                        {"featureId": "abc", "featureType": "extrude", "createdFaceCount": 4},
                        {"featureId": "def", "featureType": "fillet", "createdFaceCount": 2},
                    ]
                }
            }
        }

        rows = extract_feature_fingerprints(payload)

        self.assertEqual(set(rows.keys()), {"abc", "def"})
        self.assertEqual(rows["abc"]["createdFaceCount"], 4)


if __name__ == "__main__":
    unittest.main()
