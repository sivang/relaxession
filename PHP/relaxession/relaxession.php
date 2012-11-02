<?php
require "/home/sivan/couch-php/phpillow/src/bootstrap.php";
include "mysessiondocument.php";

// needed to workaround a possible bug in the autoload mechanism of PHP
// being investigated by Kord Nordman from Arbitracker
new phpillowStatusResponse( array() );

class MySessionHandler
{
    public function open($save_path, $session_name)
    // make sure the session db is existant
    {
    	phpillowConnection::createInstance('localhost', 5984);
	phpillowConnection::setDatabase('session_store');
	$db = phpillowConnection::getInstance();
	try
	{
		$db->put('/session_store');
	}
	catch ( Exception $e ) { /* db exists, ignore */ };
    	return true;
    }
    
    public function close()
    {
      	return true;
    }
    
    public function read($id)
    {
    	$doc = new mySessionDocument();
	try
	{
	$doc->fetchById("sess-$id");
	}
	catch (Exception $e) { return false; }
      	return (string) $doc->session_data;
    }
    
    public function write($id, $sess_data)
    {
    	$doc = new mySessionDocument();
	try
	{
		$doc->fetchById("sess-$id");
	} catch (Exception $e) { /* ignore, we are storing a new session */ };
	$doc->session_id = $id;
	$doc->timestamp = time();
	$doc->session_data = $sess_data;
	$doc->save();
    
    }
    
    function destroy($id)
    {
    	try
	{ 
		$db->del("/session_store/sess-$id");
	} 
	catch (Exception $e) { return false;};
	return true;
    }
    
    function gc($maxlifetime)
    {
        return true;
    }
}

    $session_handler = new MySessionHandler();
    session_set_save_handler(
        array($session_handler, "open"),
        array($session_handler, "close"),
        array($session_handler, "read"),
        array($session_handler, "write"),
        array($session_handler, "destroy"),
        array($session_handler, "gc")); 

?>
