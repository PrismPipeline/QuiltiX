import argparse
import site

def main():
    parser = argparse.ArgumentParser(description='My script description')
    parser.add_argument('--site', required=True, help='Path to site-packages folder')
    args = parser.parse_args()

    site_packages_folder = args.site
    site.addsitedir(site_packages_folder)

    from QuiltiX import quiltix
    quiltix.launch()

if __name__ == "__main__":
    main()
