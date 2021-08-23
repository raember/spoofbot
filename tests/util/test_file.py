import unittest
from pathlib import Path

from spoofbot.util import get_symlink_path, to_filepath, to_url


class PathTraversalTest(unittest.TestCase):
    def test_same_dir(self):
        root = Path('.')
        from_path = root / 'path/to/file1.cache'
        to_path = root / 'path/to/file2.cache'
        self.assertEqual('file2.cache', str(get_symlink_path(from_path, to_path, root)))

    def test_path_traversal_same_level(self):
        root = Path('.')
        from_path = root / 'path/to1/file1.cache'
        to_path = root / 'path/to2/file2.cache'
        self.assertEqual('../to2/file2.cache', str(get_symlink_path(from_path, to_path, root)))

    def test_path_traversal_parent_dir(self):
        root = Path('.')
        from_path = root / 'path/to/file.cache'
        to_path = root / 'path/to.cache'
        self.assertEqual('../to.cache', str(get_symlink_path(from_path, to_path, root)))

    def test_path_traversal_child_dir(self):
        root = Path('.')
        from_path = root / 'path/to.cache'
        to_path = root / 'path/to/file.cache'
        self.assertEqual('to/file.cache', str(get_symlink_path(from_path, to_path, root)))

    def test_path_traversal_deep_root(self):
        root = Path('deep/root/dir')
        from_path = root / 'path/to1/file1.cache'
        to_path = root / 'path/to2/file2.cache'
        self.assertEqual('../to2/file2.cache', str(get_symlink_path(from_path, to_path, root)))

    def test_path_traversal_deep_root_fail(self):
        root = Path('deep/root/dir')
        from_path = Path('deep/root/path/to1/file1.cache')
        to_path = Path('deep/root/path/to2/file2.cache')
        with self.assertRaises(ValueError):
            print(get_symlink_path(from_path, to_path, root))


class UrlToPathMappingTest(unittest.TestCase):
    def test_url_to_path(self):
        url = 'https://example.com:443/app=/?var=\\some /val&key=ä'
        root = Path('.cache')
        path = root / 'example.com:443/app=/?var=%5Csome+%2Fval/key=%C3%A4.cache'
        self.assertEqual(str(path), str(to_filepath(url, root)))

    def test_url_to_path2(self):
        url = 'https://example.com/?key=val&_=0'
        root = Path('.cache')
        path = root / 'example.com/?key=val.cache'
        self.assertEqual(str(path), str(to_filepath(url, root)))

    def test_path_to_url(self):
        url = 'https://example.com:443/app=?var=\\some /val&key=ä'
        root = Path('.cache')
        path = root / 'example.com:443/app=/?var=%5Csome+%2Fval/key=%C3%A4.cache'
        self.assertEqual(url, to_url(path, root).url)


if __name__ == '__main__':
    unittest.main()
