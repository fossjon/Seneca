#!/usr/bin/perl

use strict;
use POSIX;
use Sys::Hostname;
use Time::Local;
use LWP::Simple;

require "syscall.ph";

sub trim
{
	my ($result) = @_;
	
	$result =~ s/^\s+//ig;
	$result =~ s/\s+$//ig;
	
	return $result;
}

sub safesplit
{
	my ($seprchar, $maxmsize, $inptstri) = @_;
	$inptstri =~ s/$seprchar+/$seprchar/ig;
	my @result = split($seprchar, $inptstri);
	
	my $listsize = @result;
	
	while ($listsize < $maxmsize)
	{
		push(@result, "");
		$listsize += 1;
	}
	
	return @result;
}

sub mntcheck
{
	my @result;
	
	open(FILEOBJC, "</proc/mounts");
	my @linelist = <FILEOBJC>;
	close(FILEOBJC);
	
	foreach (@linelist)
	{
		my $lineitem = $_;
		
		$lineitem = trim($lineitem);
		
		if ($lineitem =~ m/^[^ \t]*\/[^ \t]+[ \t].*$/i)
		{
			$lineitem =~ s/[ \t]+/ /ig;
			
			my @infolist = safesplit(" ", 4, $lineitem);
			my @optslist = safesplit(",", 2, $infolist[3]);
			
			my @templist = ($infolist[0], $infolist[1], $infolist[2], $optslist[0]);
			push(@result, \@templist);
		}
	}
	
	return @result;
}

sub modetype
{
	my ($modenumb) = @_;
	
	my $S_IFDIR = 16384;
	my $S_IFREG = 32768;
	
	if (($S_IFDIR & $modenumb) > 0)
	{
		return "d";
	}
	
	if (($S_IFREG & $modenumb) > 0)
	{
		return "-";
	}
	
	return "?";
}

sub permpars
{
	my ($modenumb) = @_;
	my $result = "";
	
	my @ownrlist = (["u", 6], ["g", 3], ["o", 0]);
	my @permlist = (["r", 4], ["w", 2], ["x", 1]);
	my @speclist = (["u", 4, "s", "S"], ["g", 2, "s", "S"], ["o", 1, "t", "T"]);
	
	foreach (@ownrlist)
	{
		my @ownritem = @$_;
		my $ownrnumb = (($modenumb >> $ownritem[1]) & 7);
		
		foreach (@permlist)
		{
			my @permitem = @$_;
			my $permnumb = ($ownrnumb & $permitem[1]);
			
			my $permchar = "-";
			
			if ($permnumb > 0)
			{
				$permchar = $permitem[0];
			}
			
			foreach (@speclist)
			{
				my @specitem = @$_;
				my $specnumb = (($modenumb >> 9) & $specitem[1]);
				
				if (($specitem[0] eq $ownritem[0]) && ("x" eq $permitem[0]) && ($specnumb > 0))
				{
					$permchar = $specitem[2];
					
					if ($permnumb < 1)
					{
						$permchar = $specitem[3];
					}
				}
			}
			
			$result = ($result.$permchar);
		}
	}
	
	return $result;
}

sub statfs
{
	my ($dirname) = @_;
	
	my $buff = "\0"x128;
	
	syscall(&SYS_statfs, $dirname, $buff);
	
	my ($sysname, $nodename, $release, $version, $machine) = POSIX::uname();
	my ($bsize, $blocks, $bfree, $bavail, $files, $ffree, $namelen) = unpack("x4 L6 x8 L", $buff);
	
	if ($machine eq "x86_64")
	{
		($bsize, $blocks, $bfree, $bavail, $files, $ffree, $namelen) = unpack("x8 L1 x4 L1 x4 L1 x4 L1 x4 L1 x4 L1", $buff);
	}
	
	return (($bavail * 100) / $blocks);
}

sub kojiproc
{
	my @result;
	
	open(FILEOBJC, "</sys/fs/cgroup/systemd/system/kojid.service/cgroup.procs");
	my @procnums = <FILEOBJC>;
	close(FILEOBJC);
	
	foreach (@procnums)
	{
		my $procnumb = $_;
		
		$procnumb = trim($procnumb);
		
		open(FILEOBJC, "</proc/".$procnumb."/cmdline");
		my $proccomd = "";
		
		while (<FILEOBJC>)
		{
			$proccomd = $_;
			$proccomd = trim($proccomd);
			last;
		}
		
		close(FILEOBJC);
		
		$proccomd =~ s/\0/ /ig;
		
		if ($proccomd ne "")
		{
			push(@result, $procnumb);
		}
	}
	
	return @result;
}

sub certdate
{
	my ($datestri) = @_;
	my $result = 0;
	
	my @datelist = safesplit(" ", 5, $datestri);
	my @timelist = safesplit(":", 3, $datelist[2]);
	my $monthstr = $datelist[0];
	my %monthlst = ("Jan"=>0, "Feb"=>1, "Mar"=>2, "Apr"=>3, "May"=>4, "Jun"=>5, "Jul"=>6, "Aug"=>7, "Sep"=>8, "Oct"=>9, "Nov"=>10, "Dec"=>11);
	
	$result = timelocal($timelist[2], $timelist[1], $timelist[0], $datelist[1], $monthlst{$monthstr}, $datelist[3]);
	
	if (($datelist[4] eq "UTC") || ($datelist[4] eq "GMT"))
	{
		$result = timegm($timelist[2], $timelist[1], $timelist[0], $datelist[1], $monthlst{$monthstr}, $datelist[3]);
	}
	
	return $result;
}

sub kojicert
{
	my $conffile = "/etc/kojid/kojid.conf";
	
	open(FILEOBJC, "<".$conffile);
	my @linelist = <FILEOBJC>;
	close(FILEOBJC);
	
	my $listleng = @linelist;
	
	if ($listleng < 1)
	{
		return (2, "Koji configuration file [".$conffile."] is either non-existent, or empty!");
	}
	
	my $certfile = "";
	
	foreach (@linelist)
	{
		my $lineread = $_;
		
		$lineread = trim($lineread);
		
		if ($lineread =~ m/^[ \t]*cert[ \t]*=[ \t]*(.*)$/i)
		{
			$certfile = $lineread;
			$certfile =~ s/^[ \t]*cert[ \t]*=[ \t]*//i;
			$certfile = trim($certfile);
		}
	}
	
	open(FILEOBJC, "<".$certfile);
	@linelist = <FILEOBJC>;
	close(FILEOBJC);
	
	$listleng = @linelist;
	
	if ($listleng < 1)
	{
		return (2, "Koji certificate file [".$certfile."] is either mis-configured, non-existent, or empty!");
	}
	
	my $valiflag = "";
	my $befrtime = "";
	my $aftrtime = "";
	
	foreach (@linelist)
	{
		my $lineread = $_;
		
		$lineread = trim($lineread);
		
		if (($valiflag eq "") && ($lineread =~ m/^[ \t]*validity[ \t]*$/i))
		{
			$valiflag = "true";
		}
		
		if (($valiflag ne "") && ($befrtime eq "") && ($lineread =~ m/^[ \t]*not[ \t]*before[ \t]*:[ \t]*(.*)$/i))
		{
			$befrtime = $lineread;
			$befrtime =~ s/^[ \t]*not[ \t]*before[ \t]*:[ \t]*//i;
			$befrtime = trim($befrtime);
		}
		
		if (($valiflag ne "") && ($befrtime ne "") && ($aftrtime eq "") && ($lineread =~ m/^[ \t]*not[ \t]*after[ \t]*:[ \t]*(.*)$/i))
		{
			$aftrtime = $lineread;
			$aftrtime =~ s/^[ \t]*not[ \t]*after[ \t]*:[ \t]*//i;
			$aftrtime = trim($aftrtime);
		}
	}
	
	if (($befrtime eq "") || ($aftrtime eq ""))
	{
		return (2, "Could not parse certificate [".$certfile."] expirey times: not before [".$befrtime."] and not after [".$aftrtime."]!");
	}
	
	my $prestime = time();
	my $befrchek = certdate($befrtime);
	my $aftrchek = certdate($aftrtime);
	
	my $goodflag = "";
	
	if (($befrchek <= $prestime) && ($prestime <= $aftrchek))
	{
		$goodflag = "true";
	}
	
	if ($goodflag ne "true")
	{
		my $presstri = (gmtime()." GMT");
		
		return (2, "System date [".$presstri."] did not match Certificate expirey from [".$befrtime."] to [".$aftrtime."]!");
	}
	
	return (0, "");
}

sub kojidate
{
	my ($datestri, $timezone) = @_;
	my $result = 0;
	
	my @templist = safesplit(" ", 2, $datestri);
	my @datelist = safesplit("-", 3, $templist[0]);
	my @timelist = safesplit(":", 3, $templist[1]);
	
	$result = timelocal($timelist[2], $timelist[1], $timelist[0], $datelist[2], $datelist[1] - 1, $datelist[0]);
	
	if (($timezone eq "UTC") || ($timezone eq "GMT"))
	{
		$result = timegm($timelist[2], $timelist[1], $timelist[0], $datelist[2], $datelist[1] - 1, $datelist[0]);
	}
	
	return $result;
}

sub kojistat
{
	my $rooturls = "http://arm.koji.fedoraproject.org";
	my $hosturls = ($rooturls."/~koji/koji.hosts.txt");
	my $kojiurls = ($rooturls."/koji/hostinfo?hostID=");
	
	my $hostname = hostname;
	my $hostnumb = -1;
	my $pagedata = get($hosturls);
	my @linelist = safesplit("\n", 2, $pagedata);
	
	foreach (@linelist)
	{
		my $lineread = $_;
		
		$lineread = trim($lineread);
		
		if ($lineread =~ m/^[0-9]+ $hostname$/i)
		{
			my $tempnumb = $lineread;
			
			$tempnumb =~ s/ .*$//ig;
			$hostnumb = int($tempnumb);
			
			if ($hostnumb ne $tempnumb)
			{
				$hostnumb = -1;
			}
		}
	}
	
	if ($hostnumb < 0)
	{
		return (1, "Could not find Koji host number for Koji host [".$hostnumb."].");
	}
	
	$pagedata = get($kojiurls.$hostnumb);
	$pagedata =~ s/[\0\t\r\n]/ /ig;
	$pagedata =~ s/[ ]+</</ig;
	$pagedata =~ s/<tr/\n<tr/ig;
	@linelist = safesplit("\n", 2, $pagedata);
	
	my $mdaynumb;
	my $monthstr;
	my $yearnumb;
	my $timestri;
	my $timezone = "LOCAL";
	my $prestime = 0;
	
	foreach (@linelist)
	{
		my $lineread = $_;
		
		$lineread = trim($lineread);
		
		if ($lineread =~ m/^.*<span id=['"]loginInfo['"]>.*$/i)
		{
			my $tempzone = $lineread;
			
			$tempzone =~ s/^.*<span id=['"]loginInfo['"]>//i;
			$tempzone =~ s/<\/span>.*$//i;
			
			($mdaynumb, $monthstr, $yearnumb, $timestri, $timezone) = ($tempzone =~ m/^.*[A-Z][a-z]+,[ ]+([0-9]+)[ ]+([A-Z][a-z]+)[ ]+([0-9]+)[ ]+([0-9]+:[0-9]+:[0-9]+)[ ]+([^ ]+).*$/i);
			$prestime = certdate("$monthstr $mdaynumb $timestri $yearnumb $timezone");
		}
	}
	
	my $enabstat = 0;
	my $redystat = 0;
	my @tasklist;
	my $lastchek = 0;
	my $chektime = (4 * 60);
	my $tasktime = (8 * 3600);
	
	foreach (@linelist)
	{
		my $lineread = $_;
		
		$lineread = trim($lineread);
		
		if ($lineread =~ m/^<tr><th>Enabled.<\/th>.*<img [^>]*src=['"][^>]*\/yes.png['"][^>]*>.*$/i)
		{
			$enabstat = 1;
		}
		
		if ($lineread =~ m/^<tr><th>Ready.<\/th>.*<img [^>]*src=['"][^>]*\/yes.png['"][^>]*>.*$/i)
		{
			$redystat = 1;
		}
		
		if ($lineread =~ m/^<tr.*<td><a href=['"]buildrootinfo.buildrootID=[0-9]+['"]>[^<]+<\/a><\/td>.*$/i)
		{
			my $lineinfo = $lineread;
			
			$lineinfo =~ s/^<tr.*<td><a href=['"]buildrootinfo.buildrootID=[0-9]+['"]>[^<]+<\/a><\/td><td>//i;
			$lineinfo =~ s/<\/td>.*$//i;
			
			my $tasktime = kojidate($lineinfo, $timezone);
			
			$lineinfo = $lineread;
			
			$lineinfo =~ s/^<tr.*<td><a href=['"]buildrootinfo.buildrootID=//i;
			$lineinfo =~ s/['"].*$//i;
			
			my @taskinfo = ($lineinfo, $tasktime);
			
			push(@tasklist, \@taskinfo);
		}
		
		if ($lineread =~ m/^<tr><th>Last Update<\/th>.*$/i)
		{
			my $lineinfo = $lineread;
			
			$lineinfo =~ s/^<tr><th>Last Update<\/th><td>//i;
			$lineinfo =~ s/<\/td>.*$//i;
			
			$lastchek = kojidate($lineinfo, $timezone);
		}
	}
	
	if ($enabstat != 1)
	{
		return (1, "Koji host is not enabled.");
	}
	
	my $taskleng = @tasklist;
	
	if (($redystat != 1) && ($taskleng < 1))
	{
		return (2, "Host is not ready with no tasks!");
	}
	
	foreach (@tasklist)
	{
		my @taskitem = @$_;
		
		if (($prestime - $tasktime) >= $taskitem[1])
		{
			return (1, "Task [".$rooturls."/koji/buildrootinfo?buildrootID=".$taskitem[0]."] has been running for over [".($tasktime / 3600)."] hours.");
		}
	}
	
	if (($prestime - $chektime) >= $lastchek)
	{
		return (1, "Host has not checked in during the last [".($chektime / 60)."] minutes.");
	}
	
	return (0, $taskleng);
}

sub concat
{
	my ($result) = @_;
	
	if ($result ne "")
	{
		$result = ($result." - ");
	}
	
	return $result;
}

sub eol
{
	return "\n";
}

sub main
{
	my $result = "";
	
	# check all mount points
	
	my @mntlist = mntcheck();
	
	foreach (@mntlist)
	{
		my @infolist = @$_;
		
		if ($infolist[3] ne "rw")
		{
			print("Mount point [$infolist[0] $infolist[1] $infolist[2] $infolist[3]] is not read/write!".eol());
			exit(2);
		}
	}
	
	$result = (concat($result)."Mounts [Options OK]");
	
	# check common directories and files permissions
	
	my @filelist = (["/","dr.xr-xr-x root root"], ["/tmp","drwxrwxrwt root root"], ["/var/log","drwxr-xr-x root root"], ["/var/lib/mock","drwxrwsr-x root mock"], ["/var/cache/mock","drwxrwsr-x root mock"]);
	
	foreach (@filelist)
	{
		my @infolist = @$_;
		my @statinfo = stat($infolist[0]);
		
		my $filetype = modetype($statinfo[2]);
		my $permstri = permpars($statinfo[2]);
		my $usernumb = getpwuid($statinfo[4]);
		my $grupnumb = getgrgid($statinfo[5]);
		
		my $infostri = ($filetype.$permstri." ".$usernumb." ".$grupnumb);
		
		if ($infostri !~ m/^$infolist[1]$/i)
		{
			print("Permissions differ for [".$infolist[0]."] : Found [".$infostri."] - Expected [".$infolist[1]."].".eol());
			exit(2);
		}
	}
	
	$result = (concat($result)."Dirs [Perms OK]");
	
	# check common directories and files sizes
	
	foreach (@filelist)
	{
		my @infolist = @$_;
		
		if (substr($infolist[1], 0, 1) eq "d")
		{
			my $dirsize = statfs($infolist[0]);
			
			if ($dirsize < 5)
			{
				print("Directory [".$infolist[0]."] size is really low [".$dirsize."% free]!".eol());
				exit(2);
			}
			
			if ($dirsize < 10)
			{
				print("Directory [".$infolist[0]."] size is getting low [.".$dirsize."% free].".eol());
				exit(1);
			}
		}
	}
	
	$result = (concat($result)."Dirs [Sizes OK]");
	
	# check related koji config options
	
	my @certchek = kojicert();
	
	if ($certchek[0] != 0)
	{
		print($certchek[1].eol());
		exit($certchek[0]);
	}
	
	$result = (concat($result)."System [Time OK]");
	$result = (concat($result)."Koji [Config OK]");
	$result = (concat($result)."Koji [Cert OK]");
	
	# check for koji process
	
	my @kojilist = kojiproc();
	my $kojileng = @kojilist;
	
	if ($kojileng < 1)
	{
		print("No Koji processes found running!".eol());
		exit(2);
	}
	
	$result = (concat($result)."Koji [".$kojileng." Procs OK]");
	
	# check the koji host state
	
	my @kojiinfo = kojistat();
	
	if ($kojiinfo[0] != 0)
	{
		print($kojiinfo[1].eol());
		exit($kojiinfo[0]);
	}
	
	$result = (concat($result)."Koji [Host OK]");
	$result = (concat($result)."Koji [Enabled OK]");
	$result = (concat($result)."Koji [Ready OK]");
	$result = (concat($result)."Koji [".$kojiinfo[1]." Tasks OK]");
	
	print($result.eol());
	exit(0);
}

main();

