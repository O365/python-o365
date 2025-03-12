Excel
=====
You can interact with new Excel files (.xlsx) stored in OneDrive or a SharePoint Document Library. You can retrieve workbooks, worksheets, tables, and even cell data. You can also write to any excel online.

To work with Excel files, first you have to retrieve a ``File`` instance using the OneDrive or SharePoint functionality.

The scopes needed to work with the ``WorkBook`` and Excel related classes are the same used by OneDrive.

This is how you update a cell value:

.. code-block:: python

    from O365.excel import WorkBook

    # given a File instance that is a xlsx file ...
    excel_file = WorkBook(my_file_instance)  # my_file_instance should be an instance of File.

    ws = excel_file.get_worksheet('my_worksheet')
    cella1 = ws.get_range('A1')
    cella1.values = 35
    cella1.update()

Workbook Sessions
-----------------

When interacting with Excel, you can use a workbook session to efficiently make changes in a persistent or nonpersistent way. These sessions become usefull if you perform numerous changes to the Excel file.

The default is to use a session in a persistent way. Sessions expire after some time of inactivity. When working with persistent sessions, new sessions will automatically be created when old ones expire.

You can however change this when creating the ``Workbook`` instance:

.. code-block:: python

    excel_file = WorkBook(my_file_instance, use_session=False, persist=False)

Available Objects
-----------------

After creating the ``WorkBook`` instance you will have access to the following objects:

* WorkSheet
* Range and NamedRange
* Table, TableColumn and TableRow
* RangeFormat (to format ranges)
* Charts (not available for now)

Some examples:

Set format for a given range

.. code-block:: python

    # ...
    my_range = ws.get_range('B2:C10')
    fmt = myrange.get_format()
    fmt.font.bold = True
    fmt.update()
    
Autofit Columns:

.. code-block:: python

    ws.get_range('B2:C10').get_format().auto_fit_columns()

Get values from Table:

.. code-block:: python

    table = ws.get_table('my_table')
    column = table.get_column_at_index(1)
    values = column.values[0]  # values returns a two-dimensional array.
