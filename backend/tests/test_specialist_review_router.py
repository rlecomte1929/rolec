import unittest
from unittest import mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import models
from backend.app.routers import specialist_review as sr


SCHEMA_TABLES = [models.SpecialistReviewEvent, models.RoadmapReviewStatus]


class SpecialistReviewRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        models.Base.metadata.create_all(self.engine, tables=[t.__table__ for t in SCHEMA_TABLES])
        self.Session = sessionmaker(bind=self.engine)
        self.sl_patch = mock.patch.object(sr, "SessionLocal", self.Session)
        self.sl_patch.start()
        self.addCleanup(self.sl_patch.stop)
        self.user = {"id": "admin-1", "is_admin": True, "role": "ADMIN"}

    def _body(self, decision, items):
        return sr.SubmitBody(case_id="case-1", decision=decision, notes="n", items=items)

    def test_full_approval_releases_to_user(self):
        items = [sr.ReviewItem(step_id="s1", decision="approve", original_step={"title": "A"})]
        res = sr.submit_review(body=self._body("approved", items), user=self.user)
        self.assertTrue(res["released_to_user"])
        self.assertFalse(res["regeneration_requested"])
        with self.Session() as db:
            self.assertEqual(db.query(models.SpecialistReviewEvent).count(), 1)
            status = db.get(models.RoadmapReviewStatus, "case-1")
            self.assertTrue(status.released_to_user)

    def test_rejection_requests_regeneration(self):
        items = [sr.ReviewItem(step_id="s1", decision="reject", reason_code="WRONG_PATHWAY",
                               original_step={"title": "A"})]
        res = sr.submit_review(body=self._body("rejected", items), user=self.user)
        self.assertFalse(res["released_to_user"])
        self.assertTrue(res["regeneration_requested"])

    def test_bad_reason_code_raises_422(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            sr.ReviewItem(step_id="s1", decision="reject", reason_code="NOPE", original_step={})


if __name__ == "__main__":
    unittest.main()
