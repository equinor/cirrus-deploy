macro_rules! exit {
    ($($arg:tt)*) => {{
        std::eprintln!($($arg)*);
        std::process::exit(1);
    }};
}

pub(crate) use exit;
