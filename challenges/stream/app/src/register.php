<?php
session_start();
require 'db.php';

function bad_char_check($name) {
    $bad_chars = ['!','"','#','$','%','&','\\','\'','(',')','*','+',',','-','.','/',':',';','<','=','>','?','@','[',']','^','`','{','|','}','~'];
    foreach ($bad_chars as $c) {
        if (strpos($name, $c) !== false) return false;
    }
    return true;
}

$message = '';
$messageClass = '';

if (isset($_POST['username']) && isset($_POST['password']) && isset($_POST['confirm'])) {
    if ($_POST['password'] !== $_POST['confirm']) {
        $message = 'Passwords do not match';
        $messageClass = 'alert-danger';
    } elseif (!bad_char_check($_POST['username'])) {
        $message = 'Bad character detected, please avoid special characters in your username';
        $messageClass = 'alert-danger';
    } else {
        $db = getDB();
        try {
            $stmt = $db->prepare("insert into users (username, password) values (:u, :p)");
            $stmt->execute(['u' => $_POST['username'], 'p' => md5($_POST['password'])]);
            $message = 'Account created';
            $messageClass = 'alert-success';
        } catch (PDOException $e) {
            $message = 'That username is already taken';
            $messageClass = 'alert-danger';
        }
    }
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Streamio - Register</title>
  <link href="/css/style.css" rel="stylesheet">
</head>
<body class="sub-page">
<?php require 'header_include.php'; ?>

  <main class="login-page">
    <div class="login-block">
      <h1>Create a new account</h1>
<?php if ($message): ?>
      <div class="alert <?php echo $messageClass; ?>"><?php echo htmlspecialchars($message, ENT_QUOTES); ?></div>
<?php endif; ?>
      <form action="/register.php" method="POST">
        <div class="form-group">
          <input type="text" placeholder="Username" name="username">
        </div>
        <div class="form-group">
          <input type="password" placeholder="Choose a password" name="password">
        </div>
        <div class="form-group">
          <input type="password" placeholder="Confirm password" name="confirm">
        </div>
        <button class="btn btn-block" type="submit">Sign up</button>
      </form>
    </div>
    <p class="login-links">Already have an account? <a href="/login.php">Login</a></p>
  </main>

</body>
</html>
