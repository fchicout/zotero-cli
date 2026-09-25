from tests.home_isolation import isolate_home

# The docs suite imports the whole CLI; keep it away from the developer's
# real ~/.config/zotero-cli too (Issue #365).
isolate_home()
