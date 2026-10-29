from datetime import datetime, timezone
from app.extensions import db


class PaidStatus:
    PAID = "paid"
    UNPAID = "unpaid"
    ALL = (PAID, UNPAID)


class Due(db.Model):
    __tablename__ = "dues"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    month = db.Column(db.String(7), nullable=False)  # e.g. "2026-09"
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    paid_status = db.Column(db.String(10), nullable=False, default=PaidStatus.UNPAID)
    paid_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        db.UniqueConstraint("user_id", "month", name="uq_due_user_month"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "resident": self.user.name if self.user else None,
            "flat_no": self.user.flat_no if self.user else None,
            "block_no": self.user.block_no if self.user else None,
            "month": self.month,
            "amount": str(self.amount),
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "paid_status": self.paid_status,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
        }
