"""v1.5.1 publication: audited Spray Studio 1.2.1; old assets are immutable."""

import release_all_v140 as release

release.TAG = 'v1.5.1'
release.OUT = release.ROOT / 'dist/release_v1.5.1'
release.REPORT = release.ROOT / 'reports/release_v1.5.1'
release.NOTES = release.ROOT / 'docs/releases/v1.5.1.md'
release.MANAGER_VERSION = '1.2.1'
release.GO_TEST_COUNT = 37
release.REQUIRE_STUDIO = True
release.REQUIRE_PROMOTION = True
release.MANAGER_ZIP = 'CSP_Spray_Manager_v1.2.1.zip'
release.SELECTOR_ZIP = 'CSP_Selector_Complete_v1.5.1.zip'
release.ALL_ZIP = 'L4D2_ESC_All_Products_v1.5.1.zip'

if __name__ == '__main__':
    release.main()
