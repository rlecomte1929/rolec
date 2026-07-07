from backend.app.services.feedback_task_engineer import compute_autonomy_tier


def test_red_for_isolation_layer():
    assert compute_autonomy_tier(task_type="Backend Implementation", complexity="Low",
                                 layer="Isolation", product_area="Core Product") == "red"


def test_red_for_auth_area():
    assert compute_autonomy_tier(task_type="Frontend Implementation", complexity="Trivial",
                                 layer="UI", product_area="Core Product", area="auth") == "red"


def test_red_for_database_migration():
    assert compute_autonomy_tier(task_type="Database Migration", complexity="Low",
                                 layer="Infrastructure", product_area="Infrastructure") == "red"


def test_green_for_trivial_ui_copy():
    assert compute_autonomy_tier(task_type="UX Redesign", complexity="Trivial",
                                 layer="UI", product_area="UX") == "green"


def test_yellow_default():
    assert compute_autonomy_tier(task_type="Backend Implementation", complexity="Medium",
                                 layer="API", product_area="Core Product") == "yellow"
