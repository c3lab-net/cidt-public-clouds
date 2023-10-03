=============================================================================
             CAIDA's Macroscopic Internet Topology Data Kit

                            ITDK 2022-02

        https://www.caida.org/catalog/datasets/internet-topology-data-kit/
=============================================================================

  NOTE: The format of the .nodes files has slightly changed.
        In ITDK release 2013-04 and earlier, we used addresses in
        0.0.0.0/8 instead of 224.0.0.0/3 for non-real addresses.

  NOTE: This README contains the full details of data collection that the
        ITDK webpage lacks, so you will want to read over this file even
        though some text duplicates the webpage (general description,
        file formats, and data use terms).

The ITDK contains data about connectivity and routing gathered
from a large cross-section of the global Internet.

At present, this ITDK release consists of

 (1) an IPv4 router-level topology,
 (2) an IPv6 router-level topology,
 (3) router-to-AS assignments,
 (4) geographic locations of routers, and
 (5) DNS lookups of all observed IP addresses.

We plan to expand this release with other complementary datasets as
they become available (more details are available at the ITDK URL
above).

The IPv4 router-level topology is derived from aliases resolved with
MIDAR and iffinder, which yield the highest confidence aliases with
very low false positives.
The IPv6 router-level topology is derived from alias resolution with
speedtrap.
The router-level topology is provided in two files, one giving the nodes
and another giving the links.  There are additional files that assign
ASes to each node, provide the geographic location of each node, and
provide the DNS name of each observed interface.


    ----------------------------------------------------------------------
    Tools used:

    * MIDAR: Monotonic ID-based Alias Resolution
      https://www.caida.org/catalog/software/midar/
      https://catalog.caida.org/details/media/2010_alias_resolution_midar

    * iffinder: Mercator-style common source address alias resolution
      https://www.caida.org/catalog/software/iffinder/

    * speedtrap: monotonic ID-based alias resolution for IPv6
      https://catalog.caida.org/paper/2013_speedtrap
      https://www.caida.org/catalog/software/scamper/

    * qrrs: bulk DNS lookup tool

    * Hoiho: DNS decoded ASN and geolocation
      https://catalog.caida.org/paper/2020_learning_extract_use_asns
      https://catalog.caida.org/paper/2021_learning_extract_geographic_information

    * MaxMind's free GeoLite2 database
      https://dev.maxmind.com/geoip/geolite2-free-geolocation-data

    * bdrmapIT for AS assignments
      https://catalog.caida.org/paper/2018_pushing_boundaries_bdrmapit
      https://dl.acm.org/doi/10.1145/3278532.3278538

    Source datasets:

    * IPv4 Routed /24 Topology Dataset
      https://www.caida.org/catalog/datasets/ipv4_routed_24_topology_dataset/

    * IPv6 Topology Dataset
      https://www.caida.org/catalog/datasets/ipv6_allpref_topology_dataset/

    Data collection:

      The MIDAR alias resolution run was performed 2022-02-25 to
      2022-03-02 on 66 monitors (in 31 countries) using:

        * 2.94 million addresses extracted from the IPv4 Routed /24
          Topology Dataset ("Ark Routed /24 traces") for the period
          2022-02-08 to 2022-02-23.  We used 32 cycles of traces
          (cycles 9854 to 9885, all from team 1) from 104 monitors
          in 38 countries -- all active Ark monitors instead of the
          subset used for MIDAR).

      (The file itdk-run-20220224.addrs.bz2 contains the target addresses
      used for the ITDK run.)

      When extracting IP addresses from traceroute paths for the purposes
      of using them as MIDAR and iffinder (see below for
      details of the iffinder run), we only include addresses that could
      potentially be routers; that is, we only include addresses that
      appeared as an intermediate hop in some traceroute path, which means
      we exclude the responding destination address from each trace.

      NOTE: Unlike the MIDAR target list, the generated router-level graphs
            also contain the responding destinations and Ark monitors as
            nodes.

      The iffinder alias resolution run was performed on 2022-02-26 during
      the MIDAR run using the same target addresses as MIDAR.  We ran
      iffinder on 58 monitors, with each monitor independently probing
      the full set of iffinder targets in a per-monitor randomized order.

      For AS assignments, we used RIPE and RouteViews BGP tables, RIR
      delegations, PeeringDB, CAIDA AS relationships inferences, and
      Hoiho hostname mapping.

      We use a combination of publicly known Internet eXchange (IX) point
      information, Hoiho hostname mapping, and MaxMind's free GeoLite2
      database to provide the geographic location (at city granularity) of
      routers in the router-level graph.

      For details of the DNS names data collection, see the section
      below describing the available DNS files and their formats.

    ----------------------------------------------------------------------

Each router-level topology is provided in two files, one giving the
nodes and another giving the links.  There are also files that
assign ASes and geolocation to each node.


IPv4 Router Topology (MIDAR + iffinder alias resolution):
========================================================

midar-iff.nodes
midar-iff.links
midar-iff.nodes.as
midar-iff.nodes.geo

IPv6 Router Topology (speedtrap IPv6 alias resolution):
======================================================

speedtrap.nodes
speedtrap.links
speedtrap.nodes.as
speedtrap.nodes.geo


File Formats:
============

.nodes

     The nodes file lists the set of interfaces that were inferred to
     be on each router.

      Format: node <node_id>:   <i1>   <i2>   ...   <in>
     Example: node N33382:  4.71.46.6 192.8.96.6 0.4.233.32

     Each line indicates that a node node_id has interfaces i_1 to i_n.
     Interface addresses in 224.0.0.0/3 (IANA reserved space for multicast)
     are not real addresses.  They were artificially generated to identify
     potentially unique non-responding interfaces in traceroute paths.

     The IPv6 dataset uses IPv6 multicast addresses (FF00::/8) to indicate
     non-responding interfaces in traceroute paths.

       NOTE: In ITDK release 2013-04 and earlier, we used addresses in
             0.0.0.0/8 instead of 224.0.0.0/3 for these non-real addresses.


.links

     The links file lists the set of routers and router interfaces
     that were inferred to be sharing each link.  Note that these are
     IP layer links, not physical cables or graph edges.  More than
     two nodes can share the same IP link if the nodes are all
     connected to the same layer 2 switch (POS, ATM, Ethernet, etc).

      Format: link <link_id>:   <N1>:i1   <N2>:i2   [<N3>:[i3] .. [<Nm>:[im]]
     Example: link L104:  N242484:211.79.48.158 N1847:211.79.48.157 N5849773

     Each line indicates that a link link_id connects nodes N_1 to
     N_m.  If it is known which router interface is connected to the
     link, then the interface address is given after the node ID
     separated by a colon (e.g., "N1:1.2.3.4"); otherwise, only the
     node ID is given (e.g., "N1").

     By joining the node and link data, one can obtain the _known_ and
     _inferred_ interfaces of each router.  Known interfaces actually
     appeared in some traceroute path.  Inferred interfaces arise when
     we know that some router N_1 connects to a known interface i_2 of
     another router N_2, but we never saw an actual interface on the
     former router.  The interfaces on an IP link are typically
     assigned IP addresses from the same prefix, so we assume that
     router N_1 must have an inferred interface from the same prefix
     as i_2.


.nodes.as

     The node-AS file assigns an AS to each node found in the nodes
     file.  We used bdrmapIT to infer the owner AS of each node.

      Format: node.AS   <node_id>   <AS>   <heuristic-tag>
     Example: node.AS N39 17645 refinement

     Each line indicates that the node node_id is owned/operated by
     the given AS, tagged with the heuristic that bdrmapIT used. There
     are five possible heuristic tags:

        1. origins: AS inferred based on the AS announcing the
	   longest matching prefixes for the router interface IP
	   addresses.

        2. lasthop: AS inferred based on the destination AS of the
	   IP addresses tracerouted.

        3. refinement: AS inferred based on the ASes of surrounding
	   routers.

        4. as-hints: AS hints embedded in PTR records checked with
	   bdrmapIT.

        5. unknown: routers that bdrmapIT could not infer an AS for.


.nodes.geo

     The node-geolocation file contains an inferred geographic
     location of each node in the nodes file, where possible.

      Format: node.geo <node_id>:   <continent>   <country>   <region> \
              <city>   <latitude>   <longitude>  <method>
     Example: node.geo N15:  NA  US  HI  Honolulu  21.2890  -157.8028  maxmind

     Each line indicates that the node node_id has the given
     geographic location.  Columns after the colon are tab-separated.
     The fields have the following meanings:

       <continent>: a two-letter continent code

		    * AF: Africa
    		    * AN: Antarctica
    		    * AS: Asia
		    * EU: Europe
		    * NA: North America
		    * OC: Oceania
		    * SA: South America

       <country>: a two-letter ISO 3166 Country Code.

       <region>: a two or three alphanumeric region code.

       <city>: city or town in ISO-8859-1 encoding (up to 255 characters).

       <latitude> and <longitude>: signed floating point numbers.

       <method>: the geolocation method which inferred the location

                    * hoiho: inferred using Hoiho's rules
		    * ix: inferred based on the known location of an IXP
		    * maxmind: inferred using maxmind


.ifaces

     This file provides additional information about all interfaces
     included in the provided router-level graphs:

      Format:  <address> [<node_id>] [<link_id>] [T] [D]

     Each of the fields in square brackets may or may not be present.

     Example:  1.0.174.107 N34980480 D
     Example:  1.0.101.6 N18137917 L537067 T

     Example:  1.28.124.57 N45020
     Example:  11.3.4.2 N18137965 L537125 T D
     Example:  1.0.175.90

     <node_id> starts with "N" and identifies the node (alias set) to which
     the address belongs.  An address may not have a node_id if no aliases
     were found.

     <link_id> starts with "L" and identifies the link to which the address is
     attached, if known.  An address will not have a link_id if it was
     obtained from a source other than traceroute or appeared only as the
     first public address in a traceroute (i.e., the source and all other hops
     preceeding this address were either private addresses or nonresponsive).

     "T" indicates that the address appeared in at least one traceroute as a
     transit hop, i.e. preceeded by at least one (public or private) address
     (including the source) and followed by at least one public address
     (including the destination).  An address does not qualify as a transit
     hop if it was seen only in these situations: it was obtained from a
     source other than traceroute; it was the source or destination of a
     traceroute; or it was the last responding public address to appear in a
     traceroute.

     "D" indicates that the address appeared in at least one traceroute as a
     responding destination hop.

     "T" and "D" are not mutually exclusive -- an address may have been a
     transit hop in one traceroute and the destination in another.

     An interface address will have "T" but not "L<link_id>" if it appeared
     only as the first public address in a traceroute.


DNS Names:
=========

There are two related DNS names datasets, and you should choose the one to
use based on your specific needs:

1. If you would like to know what the DNS names were at about the time
   that addresses were observed in the traces of the IPv4 Routed /24
   Topology Dataset used for this ITDK, then you should download the
   relevant portion of the IPv4 Routed /24 DNS Names Dataset, generated
   with qrrs, from

   https://www.caida.org/catalog/datasets/ipv4_dnsnames_dataset

   The traces used for this ITDK were collected Feb 8-23, 2022.
   You should download DNS names files a few days before and
   after this range.

2. On Mar 2, 2022, we performed additional DNS lookups with qrrs of
   the 2.94 million MIDAR addresses in order to obtain DNS names
   closer in time to the MIDAR and iffinder runs.  These more timely
   DNS lookups are better for extracting DNS-based ground truth that
   can be compared with MIDAR and iffinder results.  These DNS results
   are available in the file

          itdk-run-20220224-dns-names.txt.bz2

   Each line contains three entries separated by tabs:

          <timestamp>    <IP-address>    <DNS-name>

   where <timestamp> is the timestamp of the lookup.
   Please see the README of the IPv4 Routed /24 DNS Names
   Dataset for full details about the encoding of special characters
   in the <DNS-name> field.


=============================================================================
Data Use Terms and Conditions
=============================================================================

See https://www.caida.org/about/legal/aua/


=============================================================================
Acknowledgments
=============================================================================

This product includes GeoLite2 data created by MaxMind, available from
https://www.maxmind.com/
