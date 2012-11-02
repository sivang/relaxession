function(doc, req) 
{
	if (doc._conflicts && typeof(doc._conflicts) != "undefined")
		return true;
	else 
		return false;

}
