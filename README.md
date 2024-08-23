# Configuration Management
This is a configuration management tool that is used to manage equipment that forms part of a mobile packet backbone network, 
that is an IP network that is used to provide a backbone services to a Core Mobile network. 
This tool connects to a set of nodes and collects configuration from each of the nodes. It does that using threading, so the overall process
is very fast. 
Then it stores collected configuration in the Git repository and when it Git hooks are used to send changes to a predefined list of recipients.
This is needed to monitor the configuration of the network in its entirety. 
