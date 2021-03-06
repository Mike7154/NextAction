#!/usr/bin/env python

import logging
import argparse

# noinspection PyPackageRequirements
from todoist.api import TodoistAPI

import time
import sys
from datetime import datetime


def is_item_visible(item):
    """Returns true if the item is visible."""
    for attr in ['is_deleted', 'is_archived', 'in_history', 'checked']:
        if item[attr] == 1:
            return False
    return True


def get_subitems(items, parent_item=None):
    """Search a flat item list for child items."""
    result_items = []
    found = False
    if parent_item:
        required_indent = parent_item['indent'] + 1
    else:
        required_indent = 1
    for item in items:
        if not is_item_visible(item):
            continue
        if parent_item:
            if not found and item['id'] != parent_item['id']:
                continue
            else:
                found = True
            if item['indent'] == parent_item['indent'] and item['id'] != parent_item['id']:
                return result_items
            elif item['indent'] == required_indent and found:
                result_items.append(item)
        elif item['indent'] == required_indent:
            result_items.append(item)
    return result_items


def main():
    """Main process function."""
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--api_key', help='Todoist API Key')
    parser.add_argument('-l', '--label', help='The next action label to use', default='next_action')
    parser.add_argument('-s', '--skip_label', help = "Label to prevent next action", default="Someday")
    parser.add_argument('-d', '--delay', help='Specify the delay in seconds between syncs', default=5, type=int)
    parser.add_argument('--debug', help='Enable debugging', action='store_true')
    parser.add_argument('--inbox', help='The method the Inbox project should be processed',
                        default='none', choices=['parallel', 'serial', 'none'])
    parser.add_argument('--parallel_suffix', default='.')
    parser.add_argument('--serial_suffix', default='_')
    parser.add_argument('--hide_future', help='Hide future dated next actions until the specified number of days',
                        default=7, type=int)
    parser.add_argument('--onetime', help='Update Todoist once and exit', action='store_true')
    parser.add_argument('--nocache', help='Disables caching data to disk for quicker syncing', action='store_true')
    args = parser.parse_args()
    # Set debug
    if args.debug:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logging.basicConfig(level=log_level)

    # Check we have a API key
    if not args.api_key:
        logging.error('No API key set, exiting...')
        sys.exit(1)

    # Run the initial sync
    logging.debug('Connecting to the Todoist API')

    api_arguments = {'token': args.api_key}
    if args.nocache:
        logging.debug('Disabling local caching')
        api_arguments['cache'] = None

    api = TodoistAPI(**api_arguments)
    logging.debug('Syncing the current state from the API')
    api.sync()

    # Check the next action label exists
    labels = api.labels.all(lambda x: x['name'] == args.label)
    skip_labels = api.labels.all(lambda x: x['name'] == args.skip_label)
    if len(labels) > 0:
        label_id = labels[0]['id']
        skip_label_id = skip_labels[0]['id']
        logging.debug('Label %s found as label id %d', args.label, label_id)
    else:
        logging.error("Label %s doesn't exist, please create it or change TODOIST_NEXT_ACTION_LABEL.", args.label)
        sys.exit(1)

    def get_project_type(project_object):
        """Identifies how a project should be handled."""
        name = project_object['name'].strip()
        if name == 'Inbox':
            return args.inbox
        elif name[-1] == args.parallel_suffix:
            return 'parallel'
        elif name[-1] == args.serial_suffix:
            return 'serial'
        else:
            return 'none'

    def get_item_type(item):
        """Identifies how a item with sub items should be handled."""
        name = item['content'].strip()
        if name[-1] == args.parallel_suffix:
            return 'parallel'
        elif name[-1] == args.serial_suffix:
            return 'serial'
        else:
            return 'None'

    def add_label(item, label, skip_label):
        if label not in item['labels'] and skip_label not in item['labels']:
            labels = item['labels']
            logging.debug('Updating %s with label', item['content'])
            labels.append(label)
            items_labels_added.append(item['id'])
            api.items.update(item['id'], labels=labels)

    def remove_label(item, label):
        if label in item['labels']:
            labels = item['labels']
            logging.debug('Updating %s without label', item['content'])
            labels.remove(label)
            items_labels_removed.append(item['id'])
            api.items.update(item['id'], labels=labels)

    # Main loop
    while True:
        items_labels_added = []
        items_labels_removed = []
        try:
            api.sync()
        except Exception as e:
            logging.exception('Error trying to sync with Todoist API: %s' % str(e))
        else:
            for project in api.projects.all():
                project_type = get_project_type(project)
                if project_type:
                    logging.debug('Project %s being processed as %s', project['name'], project_type)

                    # Get all items for the project, sort by the item_order field.
                    items = sorted(api.items.all(lambda x: x['project_id'] == project['id']), key=lambda x: x['item_order'])

                    # Tracks whether the first visible item at the root of the project has been found.
                    root_first_found = False
                    project_has_next_action = False
                    previous_indent = 0

                    for item in items:

                        if not is_item_visible(item):
                            continue

                        # If its too far in the future, remove the next_action tag and skip
                        if args.hide_future > 0 and 'due_date_utc' in item.data and item['due_date_utc'] is not None:
                            due_date = datetime.strptime(item['due_date_utc'], '%a %d %b %Y %H:%M:%S +0000')
                            future_diff = (due_date - datetime.utcnow()).total_seconds()
                            if future_diff >= (args.hide_future * 86400):
                                remove_label(item, label_id)
                                root_first_found = True
                                continue

                        item_type = get_item_type(item)
                        child_items = get_subitems(items, item)
                        item_indent = item['indent']

                        if item_indent == 1:
                            parent_type1 = item_type
                            parent_type2 = 'None'
                            parent_type3 = 'None'
                            parent_type = 'None'
                        elif item_indent == 2:
                            parent_type2 = item_type
                            parent_type3 = 'None'
                            parent_type = parent_type1
                        elif item_indent == 3:
                            parent_type3 = item_type
                            if parent_type2 =="None":
                                parent_type = parent_type1
                            else:
                                parent_type = parent_type2
                        elif item_indent == 4:
                            if parent_type3 != "None":
                                parent_type = parent_type3
                            elif parent_type2 != "None":
                                parent_type = parent_type2
                            else:
                                parent_type = parent_type1


                        if item_type =='parallel' or item_type =='serial':
                            logging.debug('Identified %s as %s type', item['content'], item_type)

                        if item_type != 'None' or len(child_items) > 0:

                            # If the project is serial and there is a next action,
                            # remove the next_action from all children.
                            if (project_type == 'serial' or parent_type == 'serial') and project_has_next_action:
                                for child_item in child_items:
                                    remove_label(child_item, label_id)
                            # Process serial tagged items
                            elif item_type == 'serial':
                                first_found = False
                                if parent_type == 'parallel' and len(child_items) > 0:
                                    remove_label(item,label_id)
                                    root_first_found = True

                                for child_item in child_items:
                                    if is_item_visible(child_item) and not first_found:
                                        add_label(child_item, label_id, skip_label_id)
                                        project_has_next_action = True
                                        first_found = True
                                    else:
                                        remove_label(child_item, label_id)
                            # Process parallel tagged items or untagged parents
                            elif item_type =='parallel' or project_type =='parallel' or parent_type == 'parallel':
                                for child_item in child_items:
                                    add_label(child_item, label_id, skip_label_id)
                                # Remove the label from the parent
                                remove_label(item, label_id)
                                root_first_found = True

                        # Process items as per project type on indent 1 if untagged
                        else:
                            if item['indent'] == 1:
                                if project_type == 'serial':
                                    if is_item_visible(item) and not root_first_found:
                                        add_label(item, label_id, skip_label_id)
                                        root_first_found = True
                                        project_has_next_action = True
                                    else:
                                        remove_label(item, label_id)
                                elif project_type == 'parallel':
                                    add_label(item, label_id, skip_label_id)



                        if label_id in item['labels'] and skip_label_id in item['labels']:
                            remove_label(item,label_id)
            if sorted(items_labels_added) == sorted(items_labels_removed):
                api.queue = []

            if len(api.queue):
                logging.debug('%d changes queued for sync... commiting to Todoist.', len(api.queue))
                api.commit()
            else:
                logging.debug('No changes queued, skipping sync.')

        # If onetime is set, exit after first execution.
        if args.onetime:
            break

        logging.debug('Sleeping for %d seconds', args.delay)
        time.sleep(args.delay)


if __name__ == '__main__':
    main()
