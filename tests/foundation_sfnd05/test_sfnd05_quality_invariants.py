from __future__ import annotations

import pytest

from app.contracts.sfnd05_api import ContractValidationError
from app.contracts.quality_flags import QualityFlags


def test_ac12_degraded_alone_without_cause_fails():
    with pytest.raises(ContractValidationError):
        QualityFlags(degraded=True)


def test_ac13_any_cause_autosets_degraded_on():
    qf = QualityFlags(stale=True, degraded=False)
    assert qf.degraded is True


def test_ac14_quarantined_true_without_other_cause_soft_allowed():
    qf = QualityFlags(quarantined=True, invalid=False, duplicate=False, out_of_order=False)
    assert qf.quarantined is True
    assert qf.degraded is True
