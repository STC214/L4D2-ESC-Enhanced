"""Current aggregate release configuration; previous release assets stay immutable."""

import release_all_v140 as release

release.TAG = 'v1.15.0'
release.OUT = release.ROOT / 'dist/release_v1.15.0'
release.REPORT = release.ROOT / 'reports/release_v1.15.0'
release.NOTES = release.ROOT / 'docs/releases/v1.15.0.md'
release.MANAGER_VERSION = '1.12.0'
release.GO_TEST_COUNT = 113
release.REQUIRE_STUDIO = True
release.REQUIRE_PROMOTION = True
release.PRERELEASE = False
release.MANAGER_ZIP = 'CSP_Spray_Manager_v1.12.0.zip'
release.SELECTOR_ZIP = 'CSP_Selector_Complete_v1.15.0.zip'
release.ALL_ZIP = 'L4D2_Tools_Portable_v1.15.0.zip'

if __name__ == '__main__':
    release.main()
