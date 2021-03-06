#!/usr/bin/env python
"""
Graph playbook folder and role dependencies for OpenShift Ansible
"""
import os
from glob import glob
import subprocess
import pygraphviz as pgv
import yaml

REPO_ROOT = '../openshift-ansible'

# This constant can be used to control which folders are excluded from the graph
SKIP_FOLDERS = [
    'adhoc',  # this folder does not provide much value to the graph
    'roles',  # roles are handled separately
    'upgrades',  # upgrades make the graph a bit complicated right now
    'files',  # these are usually heat templates
    'library',  # No yml files
    'templates',  # No yml files
    'filter_plugins',  # No yml files
    'lookup_plugins',  # No yml files
    'v3_3',  # Old upgrade playbooks
    'v3_4',  # Old upgrade playbooks
]

UNSUPPORTED_PLAYBOOKS = [
    'aws',
    'gce',
    'libvirt',
    'openstack'
]

# Uncomment this if you want to leave out unsupported playbooks
# SKIP_FOLDERS.extend(UNSUPPORTED_PLAYBOOKS)

# These are var files which are located adjacent to playbooks.
SKIP_FILES = [
    'cluster_hosts.yml',
    'vars.yml',
    'vars.defaults.yml',  # file exists in older versions
]


def git_info():
    """ Retrieves the commit date and commit description """
    git_dir = '--git-dir=%s/.git' % REPO_ROOT
    work_tree = '--work-tree=%s' % REPO_ROOT

    git_date = subprocess.check_output(
        ['git', git_dir, work_tree, 'show', '-s', '--format=%ci'])[:10]
    git_describe = subprocess.check_output(
        ['git', git_dir, work_tree, 'describe']).rstrip('\n')

    return '%s-%s' % (git_date, git_describe)


def add_subgraph(graph, path):
    """Adds a formatted subgraph to a given graph based on the path of the
    folder provided.  Returns a copy of the subgraph."""
    subgraph_style = {
        'fontname': 'bold',
        'color': 'black',
        'style': 'filled',
        'fillcolor': 'lightgrey',
        'labeljust': 'l'
    }

    # Subgraph names begin with 'cluster_' to draw them as a boxed collection
    subgraph_name = 'cluster_' + os.path.basename(path)
    subgraph_label = os.path.basename(path)

    subgraph = graph.add_subgraph(
        name=subgraph_name,
        label=subgraph_label,
        **subgraph_style)

    if subgraph_label in UNSUPPORTED_PLAYBOOKS:
        subgraph.graph_attr.update(
            color='red',
            style='filled, dashed',
            label=subgraph_label + ' (unsupported)'
        )

    return subgraph


def add_folder(graph, folder):
    """Scans a folder and
     - Adds nodes to the graph for y(a)ml files
     - Adds subgraphs for directories"""
    path = '%s/*' % folder
    for item in glob(path):
        if os.path.isfile(item) and item.lower().endswith(('.yml', '.yaml')):
            node_id = item.replace(REPO_ROOT, '')
            node_label = os.path.basename(item)
            if node_label not in SKIP_FILES:
                graph.add_node(node_id, label=node_label)
        elif os.path.isdir(item):
            if os.path.basename(item) not in SKIP_FOLDERS:
                subgraph = add_subgraph(graph, item)
                add_folder(subgraph, item)


def add_edge(graph, path):
    """Scans a y(a)ml file and adds an edge between nodes for all included
    playbooks"""

    # Skipping some files that cause errors
    if os.path.basename(path) in SKIP_FILES:
        return

    with open(path, 'r') as yaml_file:
        try:
            for task in yaml.safe_load(yaml_file.read()):
                if 'include' in task:
                    include_node_id = os.path.normpath(
                        os.path.join(os.path.dirname(path),
                                     task['include'])).replace(REPO_ROOT, '')
                    if not graph.has_node(include_node_id):
                        graph.add_node(
                            include_node_id,
                            label='Non-existent: ' + include_node_id,
                            color='red'
                        )
                    graph.add_edge(path.replace(REPO_ROOT, ''), include_node_id)
                if 'tasks' in task and task['tasks'] is not None:
                    for play_task in task['tasks']:
                        if 'include' in play_task:
                            include_node_id = os.path.normpath(
                                os.path.join(os.path.dirname(path),
                                             play_task['include'])).replace(REPO_ROOT, '')
                            if not graph.has_node(include_node_id):
                                graph.add_node(
                                    include_node_id,
                                    label='Non-existent: ' + include_node_id,
                                    color='red'
                                )
                            graph.add_edge(path.replace(REPO_ROOT, ''),
                                           include_node_id)
        except TypeError as error:
            print "TypeError: '{0}' for file: {1}".format(error, path)


def add_edges(graph, folder):
    """Scans a folder and
     - Adds an edge between nodes for y(a)ml files
     - Traverses subdirectories
    All edges are added to the root graph"""
    path = '%s/*' % folder
    for item in glob(path):
        if os.path.isfile(item) and item.lower().endswith(('.yml', '.yaml')):
            add_edge(graph, item)
        elif os.path.isdir(item):
            if os.path.basename(item) not in SKIP_FOLDERS:
                add_edges(graph, item)


def add_role_link(graph, path):
    """Scans a y(a)ml file for 'roles' tasks and adds links to the corresponding
    role node"""

    role_edge_style = {
        'color': 'blue'
    }

    # Skipping some files that cause errors
    if os.path.basename(path) in SKIP_FILES:
        return

    with open(path, 'r') as yaml_file:
        try:
            for task in yaml.safe_load(yaml_file.read()):
                if 'roles' in task:
                    for role in task['roles']:
                        if 'role' in role:
                            # Some 'roles:' include a 'role:' identifier
                            graph.add_edge(
                                path.replace(REPO_ROOT, ''),
                                os.path.join('/roles', role['role']),
                                **role_edge_style
                            )
                        else:
                            graph.add_edge(
                                path.replace(REPO_ROOT, ''),
                                os.path.join('/roles', role),
                                **role_edge_style
                            )
        except TypeError as error:
            print "TypeError: '{0}' for file: {1}".format(error, path)


def add_roles(graph, folder):
    """Scans a folder and
     - Adds a role link for y(a)ml files
     - Traverses subdirectories"""
    path = '%s/*' % folder
    for item in glob(path):
        if os.path.isfile(item) and item.lower().endswith(('.yml', '.yaml')):
            add_role_link(graph, item)
        elif os.path.isdir(item):
            if os.path.basename(item) not in SKIP_FOLDERS:
                add_roles(graph, item)


def add_role_cluster(graph, folder):
    """Creates a subgraph with a node for each directory in the roles folder.
    Add in link between dependent roles."""
    subgraph = add_subgraph(graph, folder)
    subgraph.graph_attr.update(
        color='blue'
    )
    path = '%s/*' % folder
    for item in glob(path):
        if os.path.isdir(item):
            if os.path.basename(item) not in SKIP_FOLDERS:
                node_id = item.replace(REPO_ROOT, '')
                node_label = os.path.basename(item)
                subgraph.add_node(node_id, label=node_label)

    path = '%s/*/meta/main.yml' % folder
    for item in glob(path):
        # This is ugly, fix the reliance on splitting for '3'
        dependent_role = os.path.join(folder,
                                      item.split('/')[3]).replace(REPO_ROOT, '')
        with open(item, 'r') as yaml_file:
            try:
                for dependency in yaml.load(yaml_file.read())['dependencies']:
                    if 'role' in dependency:
                        # Some 'roles:' include a 'role:' identifier
                        depended_role = os.path.join(folder,
                                                     dependency['role']).replace(REPO_ROOT, '')
                    else:
                        depended_role = os.path.join(folder,
                                                     dependency).replace(REPO_ROOT, '')
                    graph.add_edge(dependent_role, depended_role, color='red')
            except KeyError:
                pass


def main():
    """Creates the main graph, subgraphs, nodes and edges (links)"""
    git_checkout = git_info()
    root_graph_label = 'OpenShift-Ansible (%s)' % git_checkout
    root_graph = pgv.AGraph(
        strict=True,
        directed=True,
        concentrate=True,
        rankdir='LR',
        label=root_graph_label,
        labelloc='t',
        fontname='bold',
        ranksep='2.0',
        size="36,36",
        dpi="96",
    )

    root_graph.node_attr.update(
        shape='box',
        style='rounded, filled',
        color='black',
        fillcolor='white'
    )

    playbook_folder = '%s/playbooks' % REPO_ROOT
    add_folder(root_graph, playbook_folder)
    add_edges(root_graph, playbook_folder)

    role_folder = '%s/roles' % REPO_ROOT
    add_role_cluster(root_graph, role_folder)
    add_roles(root_graph, playbook_folder)

    root_graph.write('%s.dot' % git_checkout)
    root_graph.draw('%s.png' % git_checkout, prog='dot')


if __name__ == '__main__':
    main()
