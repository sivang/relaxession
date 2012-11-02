// this function gets us all the conflicts per document
// for our conflict resolution we would go over all the conflict that a document has
// and choose to make the current the most recent one. 
// We decide this by inspecting the timestamp each session document carries
function(doc) 
{
	if (doc._conflicts) 
	{
		emit(doc._conflicts);
	}

}
