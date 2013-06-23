<?php
	include "./mail/class.phpmailer.php";
	if (isset($_POST['form']))
	{
		ob_start();
	}
	else if (isset($_GET['form']))
	{
		$_GET['form'] = str_replace(" ","",$_GET['form']);
		$_GET['form'] = str_replace("\0","",$_GET['form']);
		$_GET['form'] = str_replace("\t","",$_GET['form']);
		$_GET['form'] = str_replace("\r","",$_GET['form']);
		$_GET['form'] = str_replace("\n","",$_GET['form']);
		$_GET['form'] = str_replace("\\","",$_GET['form']);
		$_GET['form'] = str_replace("/","",$_GET['form']);
		$fn = ("./ts.".$_GET['form'].".html");
		readfile($fn);
		die;
	}
?>

<html>
	<head>
		<style>
			.maxw
			{
				width: 100%;
			}
			
			.quart
			{
				width: 75%;
			}
			
			.half
			{
				width: 50%;
			}
			
			.inpt
			{
				width: 48px;
			}
			
			body, table, input
			{
				font-size: 12;
			}
			
			td
			{
				font-family: monospace;
			}
			
			a
			{
				text-decoration: none;
			}
		</style>
		
		<script>
			var init = 0, lock = 0;
			function show()
			{
				document.getElementById("extra").style.display = "";
				lock = 0;
			}
			function lten(lnum)
			{
				if (lnum < 10) { return ("0"+lnum+""); }
				return (""+lnum+"");
			}
			function secs(inpt)
			{
				var tlst = document.getElementsByName(inpt)[0].value.split(":");
				if (tlst.length != 2) { tlst = ["0", "0"]; }
				var hour = ((parseInt(tlst[0].replace(/^0+/,"")) || 0) * 60), mins = (parseInt(tlst[1].replace(/^0+/,"")) || 0);
				return (hour + mins);
			}
			function calc()
			{
				if (lock == 1) { return 0; }
				//cal
				if ((document.getElementsByName("datefrom")[0].value == "") || (document.getElementsByName("dateto")[0].value == ""))
				{
					var cal = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
					var pres = parseInt(new Date().getTime() / 1000);
					var past = [pres-(60*60*24*7),"Mon"], futu = [pres,"Mon"];
					while ((past[1] != "Sun") || (futu[1] != "Sat"))
					{
						if (past[1] != "Sun") { past[0] -= (60*60*24); past[1] = cal[new Date(past[0]*1000).getDay()]; }
						if (futu[1] != "Sat") { futu[0] += (60*60*24); futu[1] = cal[new Date(futu[0]*1000).getDay()]; }
					}
					if (document.getElementsByName("datefrom")[0].value == "")
					{
						var mm = lten(new Date(past[0]*1000).getMonth() + 1), dd = lten(new Date(past[0]*1000).getDate()), yyyy = new Date(past[0]*1000).getFullYear();
						document.getElementsByName("datefrom")[0].value = (mm+"/"+dd+"/"+yyyy);
					}
					if (document.getElementsByName("dateto")[0].value == "")
					{
						var mm = lten(new Date(futu[0]*1000).getMonth() + 1); dd = lten(new Date(futu[0]*1000).getDate()); yyyy = new Date(futu[0]*1000).getFullYear();
						document.getElementsByName("dateto")[0].value = (mm+"/"+dd+"/"+yyyy);
					}
				}
				//times
				var days = ["sun","mon","tue","wed","thu","fri","sat"];
				var week = [0,0,0];
				//days
				for (var i in days)
				{
					//weeks
					for (var j = 1; j <= 2; ++j)
					{
						var dayt = -1;
						//in-out
						for (var k = 1; k <= 2; ++k)
						{
							var inti = document.getElementsByName(days[i]+""+j+"_in"+k);
							var outi = document.getElementsByName(days[i]+""+j+"_out"+k);
							if (init == 0)
							{
								if ((1 < i) && (i < 5))
								{
									if ((k == 1) && (inti[0].value == "") && (outi[0].value == ""))
									{
										inti[0].value = "09:00";
										outi[0].value = "12:00";
									}
									if ((k == 2) && (inti[0].value == "") && (outi[0].value == ""))
									{
										inti[0].value = "13:00";
										outi[0].value = "17:00";
									}
								}
							}
							//all
							if ((inti[0].value == "") || (outi[0].value == "")) { continue; }
							if (dayt < 0) { dayt = 0; }
							dayt += ((secs(days[i]+""+j+"_out"+k) - secs(days[i]+""+j+"_in"+k)) / 60);
						}
						document.getElementsByName(days[i]+""+j+"_hours")[0].value = "";
						if ((0 <= dayt) && (dayt <= 24))
						{
							document.getElementsByName(days[i]+""+j+"_hours")[0].value = dayt;
							week[j] += dayt;
						}
					}
				}
				//final
				document.getElementsByName("week1_hours")[0].value = week[1];
				document.getElementsByName("week2_hours")[0].value = week[2];
				document.getElementsByName("total_hours")[0].value = (week[1] + week[2]);
				var rate = (parseFloat(document.getElementsByName("total_rate")[0].value) || 0);
				//document.getElementsByName("total_rate")[0].value = rate;
				document.getElementsByName("total_pay")[0].value = "";
				if (rate > 0) { document.getElementsByName("total_pay")[0].value = ((week[1] + week[2]) * rate); }
				init = 1;
			}
			function auto(objc)
			{
				if (lock == 1) { return 0; }
				var src = objc.name, dst = objc.name.replace(/_.*$/,"_in2");
				var lun = (secs(src)+60);
				if (document.getElementsByName(objc.name)[0].value != "")
				{
					document.getElementsByName(dst)[0].value = (lten(parseInt(lun/60))+":"+lten(lun%60));
				}
				calc();
			}
			function setu()
			{
				init = 1;
			}
			function post()
			{
				lock = 1;
			}
		</script>
	</head>
	
	<body onload="<?php if (isset($_POST['form'])) { echo 'post();'; } ?>calc();setu();">
		<form method="post" action="index.php" onsubmit="return false;" id="subf"><input type="hidden" name="form" value="true" /><table class="maxw">
			<tr><th colspan="14">SENECA COLLEGE</th></tr>
			<tr><th colspan="14">Temporary Support Staff Hourly Time Sheet<?php if (isset($_SERVER["PHP_AUTH_USER"])) { echo (' &nbsp; [<a href="javascript:void(0)" onclick="show();"><font color="red">'.$_SERVER['PHP_AUTH_USER'].'</font></a>]'); } ?></th></tr>
			<tr><td colspan="14"> &nbsp; </td></tr>
			
			<tr>
				<td colspan="2" align="right"><b>NAME:</b></td>
				<td colspan="5">
					<table class="maxw"><tr>
						<td>(Last)</td><td class="half"><input type="text" name="lastname" class="maxw" value="<?php echo $_POST['lastname']; ?>" /></td>
						<td>(First)</td><td class="half"><input type="text" name="firstname" class="maxw" value="<?php echo $_POST['firstname']; ?>" /></td>
					</tr></table>
				</td>
				<td colspan="3" align="right"><b>CONTRACT no.:</b></td>
				<td colspan="4"><input type="text" name="contract" class="maxw" value="<?php echo $_POST['contract']; ?>" /></td>
			</tr>
			
			<tr>
				<td colspan="2" align="right"><b>CAMPUS:</b></td>
				<td colspan="5"><input type="text" name="campus" class="maxw" value="<?php if (isset($_POST['campus'])) { echo $_POST['campus']; } else { echo 'Seneca@York'; } ?>" /></td>
				<td colspan="3" align="right"><b>DATE:</b></td>
				<td colspan="4">
					<table class="maxw"><tr>
						<td>(From)</td><td class="half"><input type="text" name="datefrom" class="maxw" value="<?php echo $_POST['datefrom']; ?>" /></td>
						<td>(To)</td><td class="half"><input type="text" name="dateto" class="maxw" value="<?php echo $_POST['dateto']; ?>" /></td>
					</tr></table>
				</td>
			</tr>
			
			<tr><td colspan="14"> &nbsp; </td></tr>
			<tr><td colspan="14"><b><font color="red">Round off your minutes to the nearest 15th, e.g., 13:00, 13:15, 13:45, 14:00</font></b></td></tr>
			<tr><td colspan="14"> &nbsp; </td></tr>
			
			<tr>
				<th colspan="7" class="half">WEEK 1</td>
				<th colspan="7" class="half">WEEK 2</td>
			</tr>
			
			<tr>
				<th>DAY</th>
				<th>IN</th>
				<th>OUT</th>
				<th>IN</th>
				<th>OUT</th>
				<th>HRS</th>
				<th>NOTES</th>
				<th>DAY</th>
				<th>IN</th>
				<th>OUT</th>
				<th>IN</th>
				<th>OUT</th>
				<th>HRS</th>
				<th>NOTES</th>
			</tr>
			
			<?php
				$days = array(
								array("SUN","sun"),
								array("MON","mon"),
								array("TUE","tue"),
								array("WED","wed"),
								array("THU","thu"),
								array("FRI","fri"),
								array("SAT","sat")
							);
				foreach ($days as $day)
				{
					print("<tr>"."\n");
					for ($w = 1; $w < 3; $w += 1)
					{
						print("<td align='right'>".$day[0]."</td>"."\n");
						for ($t = 1; $t < 3; $t += 1)
						{
							foreach (array("in","out") as $dir)
							{
								$e = "calc();";
								if (($dir == "out") && ($t == 1)) { $e = "auto(this);"; }
								print("<td><input type='text' name='".$day[1].$w."_".$dir.$t."' class='inpt' onkeyup='".$e."' value='".$_POST[$day[1].$w."_".$dir.$t]."' /></td>"."\n");
							}
						}
						print("<td><input type='text' name='".$day[1].$w."_hours' class='inpt' readonly='true' value='".$_POST[$day[1].$w."_hours"]."' /></td>"."\n");
						print("<td class='half'><input type='text' name='".$day[1].$w."_notes' class='maxw' value='".$_POST[$day[1].$w."_notes"]."' /></td>"."\n");
					}
					print("</tr>"."\n");
				}
			?>
			
			<tr>
				<td> &nbsp; </td>
				<td align="right" colspan="4">TOTAL HOURS FOR WEEK 1:</td>
				<td><input type="text" name="week1_hours" class="inpt" readonly="true" value="<?php echo $_POST['week1_hours']; ?>" /></td>
				<td> &nbsp; </td>
				<td> &nbsp; </td>
				<td align="right" colspan="4">TOTAL HOURS FOR WEEK 2:</td>
				<td><input type="text" name="week2_hours" class="inpt" readonly="true" value="<?php echo $_POST['week2_hours']; ?>" /></td>
				<td align="right"> &nbsp; </td>
			</tr>
			
			<tr><td colspan="14"> &nbsp; </td></tr>
			
			<tr>
				<td colspan="7"> &nbsp; </td>
				<td colspan="4" align="right"><b>TOTAL HOURS:</b></td>
				<td colspan="2"><input type="text" name="total_hours" class="maxw" readonly="true" value="<?php echo $_POST['total_hours']; ?>" /></td>
				<td align="right"> &nbsp; </td>
			</tr>
			
			<tr>
				<td colspan="7"> &nbsp; </td>
				<td colspan="4" align="right"><b>x RATE:</b></td>
				<td colspan="2"><input type="text" name="total_rate" class="maxw" onkeyup="calc();" value="<?php echo ''; ?>" /></td>
				<td align="right"> &nbsp; </td>
			</tr>
			
			<tr>
				<td colspan="7"> &nbsp; </td>
				<td colspan="4" align="right"><b>= TOTAL PAY:</b></td>
				<td colspan="2"><input type="text" name="total_pay" class="maxw" readonly="true" value="<?php echo ''; ?>" /></td>
				<td align="right"> &nbsp; </td>
			</tr>
			
			<tr><td colspan="14"> &nbsp; </td></tr>
			<tr><td colspan="14"> &nbsp; </td></tr>
			
			<tr>
				<td colspan="3" align="right"><b>Added To System: &nbsp; </b></td>
				<td colspan="4"></td>
				<td colspan="3" align="right"><b>Approved: &nbsp; </b></td>
				<td colspan="4"></td>
			</tr>
			
			<tr>
				<td colspan="3" align="right"> &nbsp; </td>
				<td colspan="4"><hr /></td>
				<td colspan="3" align="right"> &nbsp; </td>
				<td colspan="4"><hr /></td>
			</tr>
			
			<?php
				$_POST['email'] = str_replace(" ","",$_POST['email']);
				$_POST['email'] = str_replace("\0","",$_POST['email']);
				$_POST['email'] = str_replace("\t","",$_POST['email']);
				$_POST['email'] = str_replace("\r","",$_POST['email']);
				$_POST['email'] = str_replace("\n","",$_POST['email']);
			?>
			<tr id="extra" <?php if (isset($_POST['form'])) { echo 'style="display:none;"'; } ?> ><td colspan="14" align="right">
				<table class="maxw">
					<tr><td colspan="3"> &nbsp; </td></tr>
					<tr><td colspan="3"> &nbsp; </td></tr>
					<tr>
						<td align="right"><b>Email From (one address):</b></td>
						<td align="right" class="quart"><input type="text" name="emailfrom" class="maxw" value="<?php echo $_POST['emailfrom']; ?>" /></td>
						<td align="right" style="width:8px;"> &nbsp; </td>
					</tr>
					<tr>
						<td align="right"><b>Email To (sep by commas):</b></td>
						<td align="right" class="quart"><input type="text" name="emailto" class="maxw" value="<?php echo $_POST['emailto']; ?>" /></td>
						<td align="right" style="width:8px;"><input type="button" value="Save/Send" onclick="document.getElementById('subf').submit();"></td>
					</tr>
				</table>
			</td></tr>
		</table></form>
	</body>
</html>

<?php
	if (isset($_POST['form']))
	{
		$out = ob_get_clean();
		print($out);
		$salt = array("cpaAF8SQdhc=","PGgticbGmTQ=");
		$uniq = ($_SERVER["PHP_AUTH_USER"].".".md5($salt[0].$_SERVER["PHP_AUTH_USER"].$salt[1]));
		$fn = ("./ts.".$uniq.".html");
		file_put_contents($fn, $out);
		$mail = new PHPMailer();
		$mail->IsSendmail();
		$mail->SetFrom(trim($_POST['emailfrom']), "Rome Mail Sender");
		$mail->AddAddress(trim($_POST['emailfrom']), "Rome Mail Sender");
		foreach (explode(",", $_POST['emailto']) as $to)
		{
			$to = trim($to);
			$mail->AddAddress($to, preg_replace("/@.*$/", "", $to));
		}
		$mail->IsHTML(true);
		$mail->Subject = ("Seneca CDOT Time Sheet For - ".$_SERVER["PHP_AUTH_USER"]);
		$mail->Body = ("<a href='http://rome.proximity.on.ca/ts/index.php?form=".$uniq."'>"."Time Sheet Externally Attached For ".$_SERVER["PHP_AUTH_USER"]." - Click Here</a>"."\n");
		$mail->AddAttachment($fn);
		if (!$mail->Send()) { echo "<br /><br /><h1>Error sending: ".$mail->ErrorInfo."</h1>"; }
	}
?>

