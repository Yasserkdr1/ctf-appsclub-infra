<?php
session_start();
require 'db.php';

$error = '';
$loggedIn = false;
$flag = '';

if (isset($_POST['username']) && isset($_POST['password'])) {
    $user = $_POST['username'];
    $pass = md5($_POST['password']);
    $db = getDB();
    $stmt = $db->prepare("select * from users where username = :username and password = :password");
    $stmt->execute(['username' => $user, 'password' => $pass]);
    $row = $stmt->fetch();
    if ($row && $user === 'Yoshi') {
        $_SESSION['logged_in'] = 1;
        $loggedIn = true;
        $flag = getenv('FLAG') ?: 'FLAG{set_the_FLAG_env_var_in_docker-compose}';
    } else {
        $error = 'Login failed';
    }
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Streamio - Login</title>
  <link href="/css/style.css" rel="stylesheet">
</head>
<body class="sub-page">
<?php require 'header_include.php'; ?>

  <main class="login-page">
    <div class="login-block">
<?php if ($loggedIn): ?>
      <h1>Welcome back, Yoshi</h1>
      <div class="alert alert-success">
        Login successful.<br>
        <code><?php echo htmlspecialchars($flag, ENT_QUOTES); ?></code>
      </div>
<?php else: ?>
      <h1>Log into your account</h1>
<?php if ($error): ?>
      <div class="alert alert-danger"><?php echo htmlspecialchars($error, ENT_QUOTES); ?></div>
<?php endif; ?>
      <form action="/login.php" method="POST">
        <div class="form-group">
          <input type="text" placeholder="Username" name="username">
        </div>
        <div class="form-group">
          <input type="password" placeholder="Password" name="password">
        </div>
        <button class="btn btn-block" type="submit">Login</button>
      </form>
<?php endif; ?>
    </div>
    <p class="login-links">Don't have an account? <a href="/register.php">Register</a></p>
  </main>

</body>
</html>
