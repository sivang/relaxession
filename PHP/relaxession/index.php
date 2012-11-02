<?php
include "relaxession.php";

session_start(); 

if (isset($_SESSION['views']))
	$_SESSION['views'] += 1;
else
	$_SESSION['views'] = 1;

$v = $_SESSION['views'];

echo "<h3> This page has been viewed by you for $v times! </h3>";

?>
