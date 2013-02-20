<?php
	$file_db = new PDO("sqlite:/home/kojiadmin/follow/.koji-follow.state.db");
	$result_list = $file_db->query("SELECT * FROM packages;");
	$js_out = "";
	foreach ($result_list as $row_item)
	{
		if ($js_out != "") { $js_out = ($js_out.",\n"); }
		$js_out = ($js_out.$row_item["pkg_info"]);
	}
	$js_out = str_replace("'epoch': None,","'epoch': 0,",$js_out);
	print("<script>\nvar pkg_list = [".$js_out."];\n</script>\n");
?>

<script>
	for (var i in pkg_list)
	{
		document.write(pkg_list[i]["srpm_name"]+":"+pkg_list[i]["dep_list"]+":"+pkg_list[i]["que_state"]["state"]+"<br/>\n");
	}
</script>

