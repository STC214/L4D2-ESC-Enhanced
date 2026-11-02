"""v1.5.0 publication configuration; immutable previous releases stay intact."""

import release_all_v140 as release

release.TAG = 'v1.5.0'
release.OUT = release.ROOT / 'dist/release_v1.5.0'
release.REPORT = release.ROOT / 'reports/release_v1.5.0'
release.NOTES = release.ROOT / 'docs/releases/v1.5.0.md'
release.MANAGER_VERSION = '1.2.0'
release.GO_TEST_COUNT = 33
release.REQUIRE_STUDIO = True
release.MANAGER_ZIP = 'CSP_Spray_Manager_v1.2.0.zip'
release.SELECTOR_ZIP = 'CSP_Selector_Complete_v1.5.0.zip'
release.ALL_ZIP = 'L4D2_ESC_All_Products_v1.5.0.zip'

if __name__ == '__main__':
    release.main()
