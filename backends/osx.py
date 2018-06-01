# Copyright (c) 2018, University of Bristol <www.bristol.ac.uk>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# ``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
# OF THE POSSIBILITY OF SUCH DAMAGE.
#
# Authors:
#   George Oikonomou
import glob
import subprocess
import xml.dom.minidom as dom
import backends.backend


tmp_file = '/tmp/get_ports_osx.xml'

port_patterns = [
    '/dev/tty.SLAB*',
    '/dev/tty.usbmodem*1',
]


class Backend(backends.backend.Backend):
    os = 'darwin'


class Device(object):
    search_attrs = {
        'idVendor': 'vid',
        'USB Vendor Name': 'vendor',
        'idProduct': 'pid',
        'USB Product Name': 'product',
        'USB Serial Number': 'serial'
    }

    @classmethod
    def get_search_attrs(cls):
        return cls.search_attrs.keys()

    def __init__(self, path, dom_node):
        self.path = path
        self.dom_node = dom_node
        self.pid = 0x00
        self.vid = 0x00
        self.vendor = 'unknown'
        self.product = 'unknown'
        self.serial = 'unknown'

    def set(self, key, val):
        try:
            setattr(self, self.search_attrs[key], int(val))

        except ValueError:
            setattr(self, self.search_attrs[key], val)

    def as_list(self):
        return [
            self.path,
            self.product,
            ' '.join(('VID=0x%04X' % self.vid,
                      'PID=0x%04X' % self.pid,
                      'Serial=%s' % self.serial,
                      'Vendor=%s' % self.vendor))
        ]


def node_text_cmp(node, text_iter):
    """Inspects the text inside a node. Returns the text itself if it appears
    inside text_iter. None otherwise"""
    try:
        if node.firstChild.nodeType == dom.Node.TEXT_NODE:
            s = node.firstChild.data
            return s if s in text_iter else None
    except AttributeError:
        return None


def read_iokit():
    ioreg_cmd = '/usr/sbin/ioreg -p IOService -k IODialinDevice -l -r -t -a'
    try:
        outfile = open(tmp_file, 'w')
        subprocess.call(ioreg_cmd, shell=True, stdout=outfile)
        document = dom.parse(tmp_file)
        return document
    except IOError:
        raise


def comports():
    ports = []
    devices = []

    for p in port_patterns:
        ports.extend(glob.glob(p))

    if len(ports) == 0:
        return ""

    # Invoke ioreg. This will give us an XML file of connected devices of a
    # specific class. We will then extract information from that XML file.
    doc = read_iokit()

    # Retrieve all XML <string>. One of them will contain the device port
    strings = doc.getElementsByTagName('string')

    # Inspect all those <string> elements to see if they have a data value that
    # also exists in the list of identified ports. For those elements, traverse
    # the DOM upwards and store their grand-grand-grand-grand-parent...
    # This will be the <dict> element that appears when a device gets connected
    for s in strings:
        text = node_text_cmp(s, ports)
        if text is not None:
            parent = s.parentNode.parentNode.parentNode.parentNode.parentNode
            devices.append(Device(text, parent))
            ports.remove(text)

        # Stop searching if we have found a match for all identified ports
        if len(ports) == 0:
            break

    # Traverse the list of those <dict> elements. For each element, search all
    # its children using depth=1. Collect and store relevant info.
    for device in devices:
        child = device.dom_node.firstChild
        while child is not None:
            if child.nodeType == dom.Node.ELEMENT_NODE:
                if child.tagName == 'key':
                    child_text = node_text_cmp(child, Device.get_search_attrs())
                    if child_text is not None:
                        device.set(
                            child_text,
                            child.nextSibling.nextSibling.firstChild.data)
            child = child.nextSibling

    return [d.as_list() for d in devices]
