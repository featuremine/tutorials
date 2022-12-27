from nicegui import ui


## UI
UNAVAILABLE = '-'

with ui.header().style('background-color: #3874c8').props('elevated'):
    with ui.column():
        with ui.row():
            ui.icon('monetization_on').style('top: 50%;transform: translateY(-10%)')
            ui.label('Featuremine Trading GUI')
    with ui.column().style('margin-start:auto;margin-end:right;align-items:right;'):
        selectAccount = ui.select(['1001','1002','1003']).style('width:10em;height:1em;').props(add='borderless label=Account')


with ui.expansion('orders BUY/SELL').classes('w-full'):
    with ui.row():
        with ui.column():
            with ui.row():
                selectMarket = ui.select({1001:'coinbase'}).style('width:10em;align-items:center;text-align:center;').props(add='label=Market')
                selectSecurity = ui.select({1001:'BTC-USD',1002:'ETH-USD',1003:'DOGE-USD',1004:'USDT-USD'}).style('width:10em;align-items:center;text-align:center;').props(add='label=Instrument')
                
        with ui.column():
            with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
                ui.label('bid price').style('width:10em;align-items:center;text-align:center;')
                ui.label('ask price').style('width:10em;align-items:center;text-align:center;')
            with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
                bidlabel = ui.label('123456.123456789').style('width:10em;align-items:center;text-align:center;')
                asklabel = ui.label('123457.123456789').style('width:10em;align-items:center;text-align:center;')

    with ui.row().style('height:3em'):
        pass

    with ui.row():
        with ui.column():
            pricein = ui.input(label='Price', placeholder='0.00').style('width:10em;align-items:center;text-align:center;')
        with ui.column():
            def update_askbid_checkbox(check):
                if check.sender == bidcheckbox and check.value:
                    askcheckbox.set_value(False)
                    pricein.props(add='readonly')
                    pricein.set_value(bidlabel.text)
                elif check.sender == askcheckbox and check.value:
                    bidcheckbox.set_value(False)
                    pricein.props(add='readonly')
                    pricein.set_value(asklabel.text)
                else:
                    pricein.props(remove='readonly')
            
            with ui.row().style('height:2px'):
                pass

            bidcheckbox = ui.checkbox('bid', on_change=lambda c: update_askbid_checkbox(c)).style('width:5em;height:1em;align-items:center;text-align:center;')
            askcheckbox = ui.checkbox('ask', on_change=lambda c: update_askbid_checkbox(c)).style('width:5em;height:1em;align-items:center;text-align:center;')

        with ui.column():
            with ui.row():
                def switch_qty(notional):
                    qtyin.view.label = 'Notional' if notional else 'Quantity'
                    qtyin.update()
                    qtyout.set_text('Quantity: -' if notional else 'Notional: -')
                        
                qtyin = ui.input(label='Quantity', placeholder='0.00').style('width:10em;align-items:center;text-align:center;')
                with ui.column():
                    with ui.row().style('height:7px'):
                        pass

                    notionalcheckbox = ui.checkbox('notional', on_change=lambda c: switch_qty(c.value)).style('width:5em;height:1em;align-items:center;text-align:center;')
                
                with ui.column():
                    with ui.row().style('height:5px'):
                        pass
                    qtyout = ui.label('Notional: -').style('width:10em;align-items:center;text-align:center;')

    with ui.row().style('height:3em'):
        pass

    with ui.row():
        ui.button('buy', on_click=lambda: ui.notify('buy on ask was pressed')).style('width:10em;margin-left:2em;align-items:center;text-align:center;').props('color=green')
        ui.button('sell', on_click=lambda: ui.notify('buy on bid was pressed')).style('width:10em;margin-left:2em;align-items:center;text-align:center;')

selected = []
with ui.expansion('orders list').classes('w-full'):
    with ui.row().style('margin-left:2em'):
        with ui.column().style('margin-left:2em;margin-top:1em'):
            def cancel_orders(b):
                global selected
                indices = [i for i, x in enumerate(selected) if x]
                for i in sorted(indices, reverse=True):
                    table.options['rowData'].pop(i)
                table.update()
                selected = [ x for i,x in enumerate(selected) if not x]

            ui.button('cancel', on_click=cancel_orders).style('width:10em').props('color=red')
                
    with ui.row():
        table = ui.table(options={
            'defaultColDef': {
                'minWidth': 100,
                'filter': True,
                'sortable': True,
                'cellStyle': {'textAlign': 'center'},
                'headerClass': 'font-bold'
            }, 
            'columnDefs': [
                {'headerName': '', 'field': 'enabled', 'cellRenderer': 'checkboxRenderer'},
                {'headerName': 'Order', 'field': 'order'},
                {'headerName': 'Account', 'field': 'account'},
                {'headerName': 'Security', 'field': 'security'},
                {'headerName': 'Venue', 'field': 'venue'},
                {'headerName': 'Side', 'field': 'side'},
                {'headerName': 'Price', 'field': 'price'},
                {'headerName': 'Quantity', 'field': 'quantity'},
            ],
            'rowData': [
                {'enabled': False, 'order': 1001, 'account': 1001, 'security': 1001, 'venue':1001, 'side':'buy', 'price':1.1, 'quantity':2.2 },
                {'enabled': False, 'order': 1002, 'account': 1001, 'security': 1001, 'venue':1001, 'side':'buy', 'price':1.1, 'quantity':2.2 },
                {'enabled': False, 'order': 1003, 'account': 1001, 'security': 1001, 'venue':1001, 'side':'buy', 'price':1.1, 'quantity':2.2 },
            ],
        })
        selected = [False] * len(table.options['rowData'])
        for col_def in table.view.options.columnDefs:
            col_def.cellClass = ['text-2xl','text-white-500']
        table.view.theme = 'ag-theme-balham-dark'
                
        def handle_change(sender, msg):
            selected[msg['rowIndex']] = msg['value']

        table.view.on('cellValueChanged', handle_change)

## Run
ui.run(title='Featuremine orders', reload=False, show=False)
