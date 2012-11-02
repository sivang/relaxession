use strict;
use warnings;

sub get_ips {
    my @data = @_;

    my %ifaces;
    my $current_iface;

    foreach my $line (@data) {
        if ( $line =~ /
                        ^(.+)   # (Capture in $1) Any number of characters at the beginning of the string
                        \s+     # Followed by any number of spaces
                        Link    # After which comes the work "Link"
                      /x 
           ) {
            $current_iface = $1;
        }

        $current_iface =~ s/\s+$//;

        if ( $line =~ /
                        addr                    # The word "addr"
                        \:                      # Followed by a colon ":"
                        (\d+\.\d+\.\d+\.\d+)    # Then an IP mask: nums.nums.nums.nums
                      /x
        ) {
            my $ip = $1;

            $ifaces{$current_iface} = $ip;
        }
    }

    return values %ifaces;
}

# Capture ifconfig output
my @ifcfg = `ifconfig`;

# Parse ifconfig output and get a list of IPs
my @current_server_ips = get_ips(@ifcfg);

foreach my $ip ( @current_server_ips ) {
    print "$ip\n" unless $ip =~ /127\.0\.0\.1/;
}

