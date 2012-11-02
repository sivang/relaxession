function(doc) 
{
	var now = new Date();
	if (Math.round(now.getTime()/1000) - doc.timestamp > 12*60*60 ) 
	{
		emit(doc._id, [doc._rev, doc.timestamp]);
	}

}
