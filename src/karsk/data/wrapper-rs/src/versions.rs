use semver::Version;

use std::collections::BTreeMap;
use std::fs;
use std::iter::zip;
use std::path::Path;

use crate::util::exit;

pub fn print_versions_to(path: impl AsRef<Path>, writer: &mut impl std::io::Write) {
    let mut versions: Vec<Version> = Vec::new();
    let mut aliases: BTreeMap<Version, Vec<String>> = BTreeMap::new();

    for entry in
        fs::read_dir(path).unwrap_or_else(|err| exit!("Couldn't read versions directory: {}", err))
    {
        let entry = entry.unwrap_or_else(|err| exit!("Couldn't read entry: {}", err));
        let name = entry.file_name().to_string_lossy().into_owned();
        let path = entry.path();

        if path.is_symlink() {
            // Entry is a symlink. We check whether the target is parseable as semver. If it is, we assume
            // the entry name to be an alias of the target.

            let Some(version) = fs::canonicalize(path)
                .ok()
                .and_then(|p| p.file_name().and_then(|s| s.to_str()).map(str::to_owned))
                .and_then(|n| Version::parse(n.as_str()).ok())
            else {
                // Target isn't semver. Skip.
                continue;
            };

            match aliases.get_mut(&version) {
                Some(list) => list.push(name),
                None => {
                    aliases.insert(version, vec![name]);
                }
            };
        } else if path.is_dir() {
            // Entry is a directory.

            let Ok(version) = Version::parse(name.as_str()) else {
                // Directory name isn't semver. Skip.
                continue;
            };

            versions.push(version);
        } else {
            // If it's not a directory or a symlink to a directory, we ignore this entry.
            continue;
        };
    }

    // Sort everything
    versions.sort_by(|a, b| b.cmp(a));
    aliases.values_mut().for_each(|x| x.sort());

    let version_strings = versions.iter().map(|x| x.to_string()).collect::<Vec<_>>();

    let longest_version_string = version_strings
        .iter()
        .map(|x| x.len())
        .max()
        .unwrap_or_default();

    for (version, version_string) in zip(versions, version_strings) {
        if let Some(list) = aliases.get(&version) {
            let _ = writeln!(
                writer,
                "{:longest_version_string$}\t({})",
                version_string,
                list.join(", ")
            );
        } else {
            let _ = writeln!(writer, "{}", version);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs::create_dir;
    use std::os::unix::fs::symlink;
    use testdir::testdir;

    #[test]
    fn test_versions_empty() {
        let dir = testdir!();

        let mut actual = vec![];
        print_versions_to(dir, &mut actual);

        assert!(actual.is_empty());
    }

    #[test]
    fn test_versions_with_non_versioned_entries() {
        let tmp = testdir!();
        create_dir(tmp.join("bin")).unwrap();
        create_dir(tmp.join("usr")).unwrap();

        let mut actual = vec![];
        print_versions_to(tmp, &mut actual);

        assert!(actual.is_empty());
    }

    #[test]
    fn test_versions_with_single_entry() {
        let tmp = testdir!();
        create_dir(tmp.join("1.2.3+4")).unwrap();

        let mut actual = vec![];
        print_versions_to(tmp, &mut actual);

        assert_eq!(String::from_utf8(actual).unwrap(), "1.2.3+4\n");
    }

    #[test]
    fn test_versions_with_links() {
        let tmp = testdir!();
        create_dir(tmp.join("1.2.3+4")).unwrap();
        symlink("1.2.3+4", tmp.join("stable")).unwrap();

        let mut actual = vec![];
        print_versions_to(tmp, &mut actual);

        assert_eq!(String::from_utf8(actual).unwrap(), "1.2.3+4\t(stable)\n");
    }

    #[test]
    fn test_versions_order() {
        let tmp = testdir!();
        create_dir(tmp.join("1.2.3+5")).unwrap();
        create_dir(tmp.join("1.2.3+4")).unwrap();
        create_dir(tmp.join("2.2.3+4")).unwrap();

        let mut actual = vec![];
        print_versions_to(tmp, &mut actual);

        assert_eq!(
            String::from_utf8(actual).unwrap(),
            "2.2.3+4\n1.2.3+5\n1.2.3+4\n"
        );
    }

    #[test]
    fn test_transitive_symlinks() {
        let tmp = testdir!();
        create_dir(tmp.join("1.2.3+4")).unwrap();
        symlink("1.2.3+4", tmp.join("stable")).unwrap();
        symlink("stable", tmp.join("other")).unwrap();

        let mut actual = vec![];
        print_versions_to(tmp, &mut actual);

        assert_eq!(
            String::from_utf8(actual).unwrap(),
            "1.2.3+4\t(other, stable)\n"
        );
    }

    #[test]
    fn test_with_broken_symlink() {
        let tmp = testdir!();
        create_dir(tmp.join("1.2.3+4")).unwrap();
        symlink("1.2.3+4", tmp.join("good")).unwrap();
        symlink("2.0.0", tmp.join("bad")).unwrap();

        let mut actual = vec![];
        print_versions_to(tmp, &mut actual);

        assert_eq!(String::from_utf8(actual).unwrap(), "1.2.3+4\t(good)\n");
    }
}
