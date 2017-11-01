#!/usr/bin/perl
#
# Given a list of switch specifications, for each interface on each switch in one of the
# specified VLANS for that switch, reconfigure the port to have mostly default settings
# and a specified port profile.  The format of the switch specification entries are:
#
# <switch-model>:<switch-dns-name>:vlan[,vlan,vlan...]:<template-name>
#
# 2017-03-31 bhc Original
#
# Note that after creating the SSH connection, no writing to stdout/stderr may be done because
# this I/O gets mized up with the SSH input/output streams.
#
# Modification history:
#
# 2017-04-25 bhc Interpret each VLAN list entry as a numeric VLAN ID followed by either an 'a' or a 'p'.  The 'a' suffix
#                causes the interfaces in the VLAN to have their speed/duplex to be set to auto/auto and the 'p'
#                suffix causes the interfcaes int he VLAN to have their speed/duplex setting preserved.  One of these
#                suffixes must be specified for each VLAN number.

#

use strict;

BEGIN
{
    push( @INC, "/usr/local/lib/perl" );
}

use FileHandle;
use POSIX qw(strftime);
use specssh;

my $LogFilePath = "/var/log/mass-port-profile-fix.log";

my $InputLine=0;

my $SwitchesSkipped=0;

my $Entry;
my $IntName;
my $IntPort;
my $InterfaceLine;
my $InterfacesSkipped;
my $IntVLAN;
my $PID;
my $Rest;
my $RevInterfaceLine;
my $Session;
my $SkipSwitch;
my $SleepTime=0;
my $SSH;
my $SwitchModel;
my $SwitchName;
my $SwitchSpecificationList;
my $SwitchUsername;
my $SwitchPassword;
my $SwitchVLANs;
my $Template;
my $TotalVLANs = 0;
my $VLAN;
my $VLAN_List;

my @ModIntList;

my @Output;

my @SwitchVLAN;

my $PretendMode = 1;

my $DEBUG = 1;

#
# Function to make an entry in our logfile
#
# Parameters:
#
# 1 : Text to log.  No line delimiters should be included.  The resultant log
#     entry will be prefixed with the current date & time.
#                                        

sub Log
{
    my $Text = shift @_;

    print LOGFILE strftime( "%Y-%m-%d %T", localtime(time) ), " $Text\n";
}

#
# Function to execute changes on a switch if not in pretend mode or to log what would be changed
# if in pretend mode.
#
# Parameters:
#
# 1 : Switch command to execute.
#
# 2 : Boolean value indicating whether a successful execution of the switch command
#     should be assumed only if the execution yields no output other than the next
#     switch prompt.  If this value is true, this routine will log an error and exit
#     when there is non-null output from the executed switch command.
#

sub ExecuteSwitchChange
{
    my @LocalOutput;

    my $SwitchCommand = shift @_;
    my $ExitOnNonNullOutput = shift @_;

    if ( $PretendMode )
    {
	Log "Would: $SwitchCommand";
    }
    else
    {
	Log "Sending to switch: $SwitchCommand";
	@LocalOutput = specssh::sshcmd( $Session, '.*[#]$', $SwitchCommand );

	sleep $SleepTime if $SleepTime;

	if ( $ExitOnNonNullOutput and $#LocalOutput != 0 )
	{
	    Log "ERROR: ExecuteSwitchChange(): unexpected non-null output received from switch command: $SwitchCommand";
	    foreach my $Entry (@LocalOutput) { Log( " - $Entry" ) }

	    Log "ERROR: Exiting due to this condition";
	    exit(1);
	}
    }
}

#
# Function to apply all changes to a specified interface
#

sub ModifyInterface
{
    my $Interface = shift @_;                    # Interface name
    my $PreserveSD = shift @_;                   # Preserve speed/duplex boolean

    my $IntAttr = "";
    my $IntDesc = "";
    my $IntDuplex = "";
    my $IntAccessVLAN = "";
    my $IntPortSec = "";
    my $IntSpeed = "";

    my $EndKeywordSeen = 0;
    my $InterfaceKeywordSeen = 0;

    my @LocalOutput;

    # Collect certain interface settings we want to retain before defaulting the interface configuration

    Log "Sending 'show running-config interface $Interface' to switch";

    @LocalOutput = specssh::sshcmd( $Session, '.*[#]$', "show running-config interface $Interface" );

    foreach $IntAttr (@LocalOutput)
    {
	$IntAttr =~ s/^\s+//;

	$DEBUG && Log "DEBUG: show run int returned line is: $IntAttr";

	if ( $InterfaceKeywordSeen == 0 )
	{
	    $InterfaceKeywordSeen = 1 if ( $IntAttr =~ "^interface " );
	    next;
	}
 
	if ( $IntAttr =~ '^end' )
	{
	    $EndKeywordSeen = 1;
	    last;
	}

	if ( $IntAttr =~ '^description ' )                    { $IntDesc = $IntAttr; next }
	if ( $IntAttr =~ '^duplex ' )                         { $IntDuplex = $IntAttr; next }
	if ( $IntAttr =~ '^speed ' )                          { $IntSpeed = $IntAttr; next }
	if ( $IntAttr =~ '^switchport access vlan ')          { $IntAccessVLAN = $IntAttr; next }
	if ( $IntAttr =~ '^switchport port-security maximum') { $IntPortSec = $IntAttr; next }

	# Skip these next two attributes silently

	next if ( $IntAttr =~ "^power inline auto" );
	next if ( $IntAttr =~ "^no logging event link-status");

	# Report any other interface atributes that will be dropped

	Log "INFO: Ignoring $SwitchName : $Interface attribute $IntAttr";	
    }
	
    # We must have seen both an 'interface keyword' and the closing 'end' keyword.

    if ( $InterfaceKeywordSeen == 0 )
    {
	Log "ERROR: No 'interface' keyword seen in show running-config output for $SwitchName : $Interface - skipping interface";
	$InterfacesSkipped++;
	return 1;
    }

    if ( $EndKeywordSeen == 0 )
    {
	Log "ERROR: No 'end' keyword seen in show running-config output for $SwitchName : $Interface - skipping interface";
	$InterfacesSkipped++;
	return 1;
    }

    if ( $IntPortSec eq "" )
    {
	# Default port security maximum to 2 (one for a workstation NIC and one for the voice NIC)

	$IntPortSec = "switchport port-security maximum 2";
    }
    else
    {
	my $PSM;

	( $PSM ) = ( split/\s+/, $IntPortSec )[3];
	$DEBUG && Log "DEBUG: Original port security maximum: $PSM";

	unless ( $PSM =~ "^[0-9]+\$" )
	{
	    Log "ERROR: Port security maximum not numeric for $SwitchName : $Interface - skipping interface";
	    $InterfacesSkipped++;
	    return 1;
	}

	$PSM++;

	$IntPortSec = "switchport port-security maximum $PSM";
    }

    ExecuteSwitchChange( "configure terminal", 0 );
    ExecuteSwitchChange( "default interface $Interface", 0 );

    ExecuteSwitchChange( "interface $Interface", 1 );
    ExecuteSwitchChange( "$IntDesc", 1 )       if ( $IntDesc ne "" );

    if ( $PreserveSD )
    {
	Log "Will preserve any speed/duplex settings for $Interface";

	ExecuteSwitchChange( "$IntSpeed", 1 )      if ( $IntSpeed ne "" );
	ExecuteSwitchChange( "$IntDuplex", 1 )     if ( $IntDuplex ne "" );
    }
    else
    {
	Log "Speed/duplex settings for $Interface will be droppped";
    }

    ExecuteSwitchChange( "$IntAccessVLAN", 1 ) if ( $IntAccessVLAN ne "" );
    ExecuteSwitchChange( "$IntPortSec", 1 );
    ExecuteSwitchChange( "no logging event link-status", 1 );
    ExecuteSwitchChange( "power inline auto", 1 );

    if ( $SwitchModel eq '3750' )
    {
	ExecuteSwitchChange( "srr-queue bandwidth share 1 30 35 5", 1 );
	ExecuteSwitchChange( "priority-queue out", 1 );
    }

    ExecuteSwitchChange( "no spanning-tree portfast", 0 );	 
    ExecuteSwitchChange( "source template $Template", 0 );
    ExecuteSwitchChange( "exit", 0 );
    ExecuteSwitchChange ("end", 0 );

    # Remember that we modified this interface

    push @ModIntList, $Interface;

    return 0;
}

#
# Main code
#

unless ( open( LOGFILE, ">>$LogFilePath" ) )
{
    die "Error opening $LogFilePath for append";
}

LOGFILE->autoflush(1);

Log "";
Log "Invoked";

print "\n";
print "Path to switch specification list file: ";
$SwitchSpecificationList = <STDIN>;
chomp( $SwitchSpecificationList );

unless ( open( SPEC, "<$SwitchSpecificationList" ) )
{
    print STDERR "Unable to open \"$SwitchSpecificationList\" for input\n";
    exit(1);
}

print "$SwitchSpecificationList has been opened successfully";
Log  "$SwitchSpecificationList has been opened successfully";

# Determine whether we'll run in pretend mode or not

for (;;)
{
    print "\n";
    print 'Pretend mode (yes or no) [yes] ';
    $Entry = <STDIN>;
    chomp( $Entry );

    $Entry = 'yes' unless $Entry;
    if ( $Entry ne 'yes' and $Entry ne 'no' )
    {
	print STDERR "\nPlease answer 'yes' or 'no'\n" ;
	next;
    }

    if ( $Entry eq 'yes' )
    {
	$PretendMode = 1;
	last;
    }

    if ( $Entry eq 'no' )
    {
	$PretendMode = 0;
	last;
    }

    die "Fatal logic error determining desired mode of operation";
    exit(1);
}

if ( $PretendMode )
{
    print "Script will run in pretend mode.  No changes will be made to switches\n";
}
else
{
    print "Script will run in live mode.  Changes will be made to switches\n";
}

# If we're not running in pretend mode, Prompt for number of seconds to sleep between sending
# modification commands to a switch.  Default is 1 second, and 0 may be specified.

unless ( $PretendMode )
{
    for (;;)
    {
	print "\n";
	print 'Seconds to sleep after each switch modification command is sent [1] ';
	$Entry = <STDIN>;
	chomp( $Entry );

	$Entry = '1' if ( $Entry eq "" );

	$SleepTime = $Entry;

	last if ( $SleepTime =~ '^[0-9]$' );
    
	print STDERR "\nPlease enter a numeric value or accept the default value\n" ;
	next;
    }

    Log "Sleep time of $SleepTime entered";

}

print "\n";
print "Please use a separate session to run tail -f on $LogFilePath because no subsequent output will be sent to stdout/stderr\n";
print "Press <ENTER> when ready: ";

$Entry=<STDIN>;

print "\n";

# Read all entries in the specified file

while ( $Entry = <SPEC> )
{
    chomp( $Entry );
    $Entry =~ s/\r$//;

    $InputLine++;

    ( $SwitchModel, $SwitchName, $VLAN_List, $Template ) = split ":", $Entry, 4;
 
    # Accept only expected switch models

    if ( $SwitchModel != "3750" && $SwitchModel != "3850" )
    {
	Log "ERROR: On line $InputLine, unknown switch model of \"$SwitchModel\" - skipping switch $SwitchName";
	$SwitchesSkipped++;
	next;
    }

    # Put the workstation VLANs in an array

    $SwitchVLANs = 0;
    @SwitchVLAN = ();

    while ( $VLAN_List )
    {
	( $SwitchVLAN[ $SwitchVLANs ], $Rest ) = split ",", $VLAN_List, 2;
	$SwitchVLAN[ $SwitchVLANs ] = lc( $SwitchVLAN[ $SwitchVLANs ] );
	$SwitchVLANs++;
	$VLAN_List = $Rest;
    }

    # Make sure every specified VLAN has a legal suffix

    $SkipSwitch = 0;

    foreach $VLAN (@SwitchVLAN)
    {
	unless ( $VLAN =~ '^[0-9]+a$' or  $VLAN =~ '^[0-9]+p$' )
	{
	 	Log "ERROR: On line $InputLine, no legal suffix specified for VLAN $VLAN - skipping switch $SwitchName";
		$SkipSwitch = 1;
	}
    }

    if ( $SkipSwitch )
    {
	$SwitchesSkipped++;
	next;
    }

    Log "";

    $DEBUG && Log "DEBUG: Switch model: $SwitchModel";
    $DEBUG && Log "DEBUG: Switch name: $SwitchName";
    $DEBUG && Log "DEBUG: Template: $Template";
    $DEBUG && Log "DEBUG: VLAN count: $SwitchVLANs";
    $DEBUG && Log "DEBUG: VLANs: @SwitchVLAN";

    # Start with an empty list of modified interfaces

    @ModIntList = ();

    $InterfacesSkipped = 0;

    # Log into the switch now

    Log "Logging into switch $SwitchName using ssh";

    my @Conn = specssh::EC( $SwitchName, 240 );

    if ( $Conn[0] != 1 )
    {
	Log  "ERROR: Unable to ssh into switch $SwitchName -- skipping";
	$SwitchesSkipped++;
	next;
    }

    $Session = $Conn[1];

    Log "Sleeping 5 seconds after login";

    sleep 5;

    unless ( $PretendMode )
    {
	Log  "Sending 'write' to switch";

	@Output = specssh::sshcmd( $Session, '.*[#]$', "write" );
    
	foreach $Entry ( @Output )
	{
	    Log "DEBUG: write returned $Entry";
	}
    }

    Log  "Sending 'terminal length 0' to disable pagination";

    sleep 5;

    @Output = specssh::sshcmd( $Session, '.*[#]$', "terminal length 0" );

    # Display all Gigabit interfaces & for any interface with a VLAN in the given list, apply the change.

    Log "Sending 'show interfaces status' command";

    @Output = specssh::sshcmd( $Session, '.*[#]$', "show interfaces status" );

    foreach $InterfaceLine ( @Output )
    {
	chomp $InterfaceLine;
	$InterfaceLine =~ s/\r//g;

	# Log "DEBUG: OIL is $InterfaceLine";

	( $IntPort, $Rest ) =  split ( /(\s+)/, $InterfaceLine, 2);

	next unless ( $IntPort =~ '^Gi[0-9]/0/' );

	$RevInterfaceLine = join( " ", reverse split( " ", $InterfaceLine ) );

	# Log "DEBUG: RIL is $RevInterfaceLine";

	$IntVLAN = (split( " ", $RevInterfaceLine ))[3];

	if ( $IntVLAN =~ 'trunk' )
	{
	    Log "Skipping interface $IntPort (trunk port)";
	    next;
	}

	unless ( $IntVLAN =~ "^[0-9]+\$" )
	{
	    Log "ERROR: Parsed VLAN \"$IntVLAN\" for interface $IntPort is not wholly numeric - skipping interface";
	    next;
	}

	# See if the interface is in one of the VLANs in the given list.  If so, apply all changes to it.

	foreach $VLAN (@SwitchVLAN)
	{
	    if ( "${IntVLAN}a" =~ "^${VLAN}\$" or  "${IntVLAN}p" =~ "^${VLAN}\$" )
	    {
		if ( $PretendMode )
		{
		    Log "Would modify interface $SwitchName : $IntPort (in VLAN $VLAN)";
		}
		else
		{
		    Log "Will modify interface $SwitchName : $IntPort (in VLAN $VLAN)";
		}

		my $PreserveSD = ( $VLAN =~ 'p$' );

		ModifyInterface( $IntPort, $PreserveSD );
		last;
	    }
	}
    }

    Log "Interfaces skipped on switch $SwitchName: $InterfacesSkipped";

    # If not running in pretend mode, do a show run int on all modified interfaces for this
    # switch and store the output in a file in the current directory.

    unless( $PretendMode )
    {
	my $ShowRunIntFile = "./mppf.showrunint.after.${SwitchName}";

	Log "Storing show run int information for all modified interfaces in $ShowRunIntFile";

	open( SHOWRUNINT, ">$ShowRunIntFile" ) or die "Unable to create show run int output file";

	foreach $IntPort (@ModIntList)
	{
	    @Output = specssh::sshcmd( $Session, '.*[#]$', "show run int $IntPort" );	

	    print SHOWRUNINT "show run int $IntPort output:\n";

	    foreach $Entry (@Output)
	    {
		print SHOWRUNINT "$Entry\n" unless ( $Entry =~ '^show run int ' );
	    }
	}

	close( SHOWRUNINT );
    }

    Log "Logging out of $SwitchName";

    @Output = specssh::sshcmd( $Session, '.*[#]$', "logout" );
}

Log "Switches skipped: $SwitchesSkipped";
Log "Finished";

exit(0);


