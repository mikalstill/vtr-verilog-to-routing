#!/usr/bin/python

###################################################################################
# This script executes one or more VTR tasks.
#
# Usage:
#       run_vtr_task.py <task_name1> <task_name2> ... [OPTIONS]
#
# For documentation on command line options, run with --help.
#
# Note: At least one task must be specified, either directly as a parameter or
# through the -l option.
#
# Authors: Michael Still, based on a perl script by Jason Luu and Jeff Goeders.
#
###################################################################################

import argparse
import os
import sys


VTR_FLOW_PATH = os.path.dirname(sys.argv[0])
SCRIPT_DEFAULT = 'run_vtr_flow.pl'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('tasks',
                        nargs='+')
    parser.add_argument('-parallel', '-p', '-j',
                        type=int,
                        help=('Perform parallel execution using N threads. Note: Large benchmarks '
                              'will use very large amounts of memory (several gigabytes). Because '
                              'of this, parallel execution often saturates the physical memory '
                              'requiring the use of swap memory, which will cause slower '
                              'execution. Be sure you have allocated a sufficiently large swap '
                              'memory or errors may result.'))
    parser.add_argument('-verbosity',
                        type=int,
                        help='How verbose to be, expressed as a number.')
    parser.add_argument('-scriptargs', '-s',
                        nargs=argparse.REMAINDER,
                        help=('Treat the remaining command line options as parameters '
                              'to forward to the VPR calling script (e.g. run_vtr_flow.pl).'))
    parser.add_argument('-system',
                        help='System type')
    parser.add_argument('-list', '-l',
                        help='Specify a task list file')
    parser.add_argument('-hide_runtime',
                        action='store_true',
                        help='Hide runtime estimates')
    parser.add_argument('-short_task_names',
                        action='store_true',
                        help='Show short task names')
    args = parser.parse_args()

    print('Running with the following arguments:')
    for key in args.__dict__:
        print('    %s: %s' %(key, args.__dict__[key]))

    # Read task files
    tasks = []
    for taskfile in args.tasks:
        with open(taskfile) as f:
            tasks.append(f.readlines())

    # Remove duplicate tasks
    tasks = set(tasks)

    # Check we have some tasks
    if not tasks:
        print('Incorrect usage. You must specify at least one task to execute')
        parser.print_help()
        sys.exit(1)

    # Find the longest common prefix of our tasks. I feel dirty that this is in os.path...
    common_task_prefix = os.path.commonprefix(tasks)

    # Collect task actions
    all_task_actions = []
    for task in tasks:
        task = task.rstrip()
        all_task_actions.append(generate_single_task_actions(args, task, common_task_prefix)

    # Run all the actions
    num_total_failures = run_actions(all_task_actions)

    sys.exit(num_total_failures)


def generate_single_task_actions(args, task, common_task_prefix):
    task_dir = os.path.join(VTR_FLOW_PATH, 'tasks', task)
    os.cwd(task_dir)

    # Read task config file
    config = {'sdc_dir': 'sdc',
              'script': SCRIPT_DEFAULT,
              'script_params_common': args.scriptargs,
              'cmos_tech_path': ''}

    with open(os.path.join('config/config.txt') as f:
        for line in f.readlines():
            line = line.rstrip()
            line = line.split('#')[0]

            if not line:
                continue

            key, value = line.split('=')
            key = key.strip()
            value = value.strip()

            if key in ['circuit_list_add', 'arch_list_add', 'script_params_list_add']:
                config.get(key.replace('_add', ''), []).append(value)
            elif key in ['script_params', 'script_params_common']:
                config.get('script_params_common', '').append(' ' + value)
            elif key in ['parse_file', 'qor_parse_file', 'pass_requirements_file']:
                continue
            elif key in ['circuits_dir', 'archs_dir', 'sdc_dir', 'script_path']:
                config[key.replace('_path', '')] = os.path.expanduser(value)
            elif key in ['script_path', 'cmos_tech_behavior']:
                config[key] = value
            else:
                print('Invalid option %s in configuration file for task %s.' %(key, task))
                sys.exit(1)

    if config['script'] == SCRIPT_DEFAULT:
        if not '-temp_dir' in config['script_params_common']:
            config['script_params_common'].insert(0, '-temp_dir .')
    else:
        args.hide_runtime = True

    if os.path.exists(os.path.join(VTR_FLOW_PATH, config['circuits_dir'])):
        config['circuits_dir'] = os.path.join(VTR_FLOW_PATH, config['circuits_dir'])
    elif not os.path.exists(config['circuits_dir']):
        print('Circuits directory not found (%s)' % config['circuits_dir'])
        sys.exit(1)

    if os.path.exists(os.path.join(VTR_FLOW_PATH, config['archs_dir'])):
        config['archs_dir'] = os.path.join(VTR_FLOW_PATH, config['archs_dir'])
    elif not os.path.exists(config['archs_dir']):
        print('Archs directory not found (%s)' % config['archs_dir'])
        sys.exit(1)

    if os.path.exists(os.path.join(VTR_FLOW_PATH, config['sdc_dir'])):
        config['sdc_dir'] = os.path.join(VTR_FLOW_PATH, config['sdc_dir'])
    elif not os.path.exists(config['sdc_dir']):
        config['sdc_dir'] = os.path.join(VTR_FLOW_PATH, 'sdc')

    if not config.get('circuits_list', []):
        print('No circuits specified for task %s' % task)
        sys.exit(1)

    if not config.get('archs_list', []):
        print('No architectures specified for task %s' % task)
        sys.exit(1)

    if not config.get('script_params_list'):
        config['script_params_list'] = ['']

    dups = find_duplicates(config['circuit_list'])
    if dups:
        print('Duplicate circuits specified for task %s: %s' %(task, ', '.join(dups)))

    dups = find_duplicates(config['archs_list']):
    if dups:
        print('Duplicate archhitectures specified for task %s: %s' %(task, ', '.join(dups)))

    dups = find_duplicates(config['script_params'])
    if dups:
        print('Duplicate script parameters specified for task %s: %s' %(task, ', '.join(dups)))

    # Check script
    if os.path.exists('%s/config/%s' %(config['task_dir'], config['script'])):
         script_path = '%s/config/%s' %(config['task_dir'], config['script'])
    elif os.path.exists('%s/config/%s' %(VTR_FLOW_PATH, config['script'])):
         script_path = '%s/config/%s' %(VTR_FLOW_PATH, config['script'])]
    elif os.path.exists(config['script']):
         pass
    else:
         print('Cannot find script for task %s (%s). Looked for %s/config/%s or %s/config/%s'
               %(task, config['script'], config['task_dir'], config['script'],
                 VTR_FLOW_PATH, config['script']))
         sys.exit(1)

    # Check architecture
    for arch in config['archs_list']:
        path = os.path.join(config['archs_dir'], arch)
        if not os.path.exists(path):
            print('Architecture file not found: %s' % path)
            sys.exit(1)
        if not os.path.isfile(path):
            print('Architecture file not found (not a file): %s' % path)
            sys.exit(1)

    # Check circuits
    for circuit in config['circuits_list']:
        path = os.path.join(config['circuits_dir'], circuit)
        if not os.path.exists(path):
            print('Circuit file not found: %s' % path)
            sys.exit(1)
        if not os.path.isfile(path):
            print('Circuit file not found (not a file): %s' % path)
            sys.exit(1)

    # Check CMOS techh behhavior
    



def find_duplicates(l):
    """ Find duplicates in a list."""
    e = {}
    for a in l:
        e.setdefault(a, 0)
        e[a] += 1

    for a in e:
        if e[a] > 1:
            yield a


if __name__ == '__main__':
    main()
