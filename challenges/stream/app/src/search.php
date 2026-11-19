<?php
session_start();
require 'db.php';

$search = isset($_POST['q']) ? strtolower($_POST['q']) : '';

$shitwords = [
    "/\\bALL\\b/i",            
    "/\\bNULL\\b/i",           
    "/\\bORDER\\b/i",          
    "/0x[0-9a-f]+/i",          
    "/RANDOMBLOB\\s*\\(/i",    
    "/SLEEP\\s*\\(/i",         
    "/BENCHMARK\\s*\\(/i",     
    "/WAITFOR\\s+DELAY/i",     
    "/PG_SLEEP\\s*\\(/i",      
    "/CHARINDEX\\s*\\(/i",     
    "/UNICODE\\s*\\(/i",       
    "/CONCAT\\s*\\(/i",        
    "/GROUP_CONCAT\\s*\\(/i",  
    "/sqlite_version/i",       
    "/information_schema/i",   
    "/\\bifnull\\s*\\(/i",     
    "/ or /i",                 
    "/\\b\\d+\\s*=\\s*\\d+\\b/", 
    "/--\\s*\\S/",             
];
if (isset($_POST['q'])) {
    foreach ($shitwords as $shitword) {
        if (preg_match($shitword, $search)) {
            header("Location: /blocked.php");
            exit;
        }
    }
}

$db = getDB();

if (!isset($_POST['q'])) {
    $res = $db->query("select * from movies order by movie");
} else {
    // Intentionally vulnerable: user input is concatenated directly
    // into the query instead of using a bound parameter.
    $query = "select * from movies where lower(movie) like '%" . $search . "%' order by movie";
    try {
        $res = $db->query($query);
    } catch (PDOException $e) {
        $res = false;
    }
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Streamio - Browse</title>
  <link href="/css/style.css" rel="stylesheet">
</head>
<body>
<?php require 'header_include.php'; ?>

  <section class="search-section">
    <h1>Search for a movie</h1>
    <form action="/search.php" method="POST" class="search-form">
      <input type="text" name="q" placeholder="Title..." autofocus>
      <button type="submit" class="btn">Search</button>
    </form>

    <div class="movie-list">
<?php
if ($res) {
    foreach ($res as $row) {
        // "year" must be a plain integer. Anything else (a username, a
        // hash, any other text) is rejected and shown as N/A instead of
        // being echoed back -- this is NOT a type the real movies table
        // enforces, it's checked here at display time on every row,
        // including rows synthesized by a UNION injection.
        $yearRaw = $row['year'] ?? '';
        $year = preg_match('/^-?\d+$/', (string)$yearRaw) ? $yearRaw : 'N/A';

        echo '<div class="movie-row">'
           . '<span class="movie-title">' . htmlspecialchars($row['movie'] ?? '', ENT_QUOTES) . '</span>'
           . '<span class="movie-year">' . htmlspecialchars((string)$year, ENT_QUOTES) . '</span>'
           . '<button class="btn btn-ghost" type="button" onclick="alert(\'Streaming is unavailable right now.\')">Watch</button>'
           . '</div>';
    }
} else {
    echo '';
}
?>
    </div>
  </section>

</body>
</html>
