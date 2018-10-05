NextAction
==========

A more GTD-like workflow for Todoist. Uses the REST API to add and remove a `@next_action` label from tasks.

This program looks at every list in your Todoist account.
Any list that ends with `_` or `.` is treated specially, and processed by NextAction.

Note that NextAction requires Todoist Premium to function properly, as labels are a premium feature.

mike7154 changes
============
There are things I changed that fit my preferences better
1. Projects had to be processed as parrallel, serial, or not at all. I added a 'None' option.
    - Now i can label a project as None, and a task as "serial" to process only that task in the project
    - Now the inbox doesn't clutter my @next_action label since I can make it not processed
2. You can take an item off the @next_action list by adding a @Someday tag. Now I can take specific items off the list manually


Requirements
============

* Python 2.7, Python 3.0+ is unsupported at the moment
* ```todoist-python``` package.

Activating NextAction
=====================

Sequential list processing
--------------------------
If a project or task ends with `_`, the child tasks will be treated as a priority queue and the most important will be labeled `@next_action`.
Importance is determined by order in the list

Parallel list processing
------------------------
If a project or task name ends with `.`, the child tasks will be treated as parallel `@next_action`s.
The waterfall processing will be applied the same way as sequential lists - every parent task will be treated as sequential. This can be overridden by appending `_` to the name of the parent task.

Executing NextAction
====================

You can run NexAction from any system that supports Python.

Running NextAction
------------------

NextAction will read your environment to retrieve your Todoist API key, so to run on a Linux/Mac OSX you can use the following commandline

    python nextaction.py -a <API Key>
