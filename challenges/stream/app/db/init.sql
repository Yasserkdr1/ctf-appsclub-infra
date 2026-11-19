CREATE TABLE users (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL 
);

CREATE TABLE movies (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    movie TEXT NOT NULL,
    year  INTEGER NOT NULL,
    apah1 INTEGER NULL,
    apah2 INTEGER NULL,
    apah3 INTEGER NULL,
    apah4 INTEGER NULL
);

-- 10 accounts with passwords taken from the real top-25 of rockyou.txt,
-- so they crack instantly with rockyou.txt. The real target, Yoshi,
-- is one of these. "admin" is a decoy: its hash cracks just as easily,
-- but login.php only ever accepts the username Yoshi.
INSERT INTO users (username, password) VALUES
    ('admin',  'e10adc3949ba59abbe56e057f20f883e'),  -- 123456   (decoy)
    ('jen',    'f25a2fc72690b780b2a14e140ef6a9e0'),  -- iloveyou (decoy)
    ('mike',   'd8578edf8458ce06fbc5bb76a58c5ca4'),  -- qwerty   (decoy)
    ('nina',   'f78f2477e949bee2d12a2c540fb6084f'),  -- tigger   (decoy)
    ('carlos', 'fc63f87c08d505264caba37514cd0cfd'),  -- nicole   (decoy)
    ('zach',  '31837932d88ae254d1a24752d0e896e3'),
    ('laura', '4a83643535651e6d902d535c7a06e77d'),
    ('guest',  'd0763edaa9d9bd2a9516280e9044d885'),  -- monkey   (decoy)
    ('test',   '0acf4539a14b3aa27deeb4cbdf6e989f'),  -- michael  (decoy)
    ('karen',  'adff44c5102fca279fce7559abf66fee'),  -- ashley   (decoy)
    ('steve',  '96e79218965eb72c92a549dd5a330112'),  -- 111111   (decoy)
    ('derek', '4f8e8f2674e5fcac957d834cf6cb5142'),
    ('Yoshi',  '4f3bdd1c5c19e6efcbe08bc8b0175da1'),  -- waapah1
    ('priya', '54b7dc82ed1077ca93338c8458dac368'),
    ('omar',  '0d29189a56d45810a91f46560356a9e1'),
    ('felix', '9b02f08a1849e5c561c130b9f8768226'),
    ('maria', 'd3e301a682e1ea08834300d0529fd3ef'),
    ('tom',   '19561fa49d32c5aa02f1c3a902d9e355'),
    ('grace', '85cc36c0808e0b441764710c549a57b7'),
    ('ivan',  '7cb1cd9cd2b836187ec6fde3cdd6b87e');

INSERT INTO movies (movie, year) VALUES
    ('The Grid Runner', 2014),
    ('Parallax Protocol', 2019),
    ('Midnight Compile', 2021),
    ('Zero Day Horizon', 2023),
    ('Carriage Return', 2017),
    ('Null Pointer Dawn', 2022),
    ('The Last Packet', 2016),
    ('Segfault City', 2020),
    ('Analog Ghosts', 2013),
    ('Recursive Sky', 2024),
    ('Firewall Season', 2018),
    ('The Quiet Exploit', 2015),
    ('Binary Tide', 2021),
    ('Static Signal', 2012),
    ('Stack Overflow Blues', 2019),
    ('The Phantom Payload', 2022),
    ('Latency', 2020),
    ('Cold Boot', 2017),
    ('Orphaned Process', 2023),
    ('Heap of Trouble', 2014),
    ('Dead Pixel Drive', 2016),
    ('The Honeypot', 2021),
    ('Root Access', 2011),
    ('Shadow IT', 2019),
    ('The Last Patch', 2024),
    ('Buffer Zone', 2013),
    ('Ciphertext', 2022),
    ('The Backdoor', 2018),
    ('Kernel Panic', 2020),
    ('Air Gap', 2023);
