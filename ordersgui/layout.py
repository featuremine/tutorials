from nicegui import ui


## UI
UNAVAILABLE = '-'

with ui.header().style('background-color: #3874c8').props('elevated'):
    ui.icon('monetization_on')
    ui.label('Featuremine Trading GUI').style('width:15em;align-items:left;text-align:left;')
    with ui.row().style('margin-start:auto;margin-end:right;align-items:right;'):
        selectAccount = ui.select(['1234']).style('width:10em;height:1em;align-items:right;text-align:right;')


with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    ui.label('Market').style('width:10em;align-items:center;text-align:center;')
    ui.label('Instrument').style('width:10em;align-items:center;text-align:center;')
with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    selectMarket = ui.select({1001:'coinbase'}).style('width:10em;align-items:center;text-align:center;')
    selectSecurity = ui.select({1001:'BTC-USD',1002:'ETH-USD',1003:'DOGE-USD',1004:'USDT-USD'}).style('width:10em;align-items:center;text-align:center;')

with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    ui.label('bid price').style('width:10em;align-items:center;text-align:center;')
    ui.label('ask price').style('width:10em;align-items:center;text-align:center;')

with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    bidlabel = ui.label(UNAVAILABLE).style('width:10em;align-items:center;text-align:center;')
    asklabel = ui.label(UNAVAILABLE).style('width:10em;align-items:center;text-align:center;')


with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    pricein = ui.input(label='Price', placeholder='0.00').style('width:8em;align-items:center;text-align:center;')
    with ui.column().style('margin-start:auto;margin-end:auto;align-items:center;'):
        def update_askbid_checkbox(check):
            if check.sender == bidcheckbox and check.value:
                askcheckbox.set_value(False)
                pricein.props(add='readonly')
            elif check.sender == askcheckbox and check.value:
                bidcheckbox.set_value(False)
                pricein.props(add='readonly')
            else:
                pricein.props(remove='readonly')
        
        bidcheckbox = ui.checkbox('bid', on_change=lambda c: update_askbid_checkbox(c)).style('width:5em;height:1em;align-items:center;text-align:center;')
        askcheckbox = ui.checkbox('ask', on_change=lambda c: update_askbid_checkbox(c)).style('width:5em;height:1em;align-items:center;text-align:center;')

with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    def switch_qty(notional):
        qtyin.view.label = 'Notional' if notional else 'Quantity'
        qtyin.update()
        qtyout.set_text('Quantity: -' if notional else 'Notional: -')
            
    qtyin = ui.input(label='Quantity', placeholder='0.00').style('width:8em;align-items:center;text-align:center;')
    notionalcheckbox = ui.checkbox('notional', on_change=lambda c: switch_qty(c.value)).style('width:5em;height:1em;align-items:center;text-align:center;')
    
with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    qtyout = ui.label('Notional: -').style('width:10em;align-items:center;text-align:center;')

with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    ui.button('buy', on_click=lambda: ui.notify('buy on ask was pressed')).style('width:9em;align-items:center;text-align:center;').props('color=green')
    ui.button('sell', on_click=lambda: ui.notify('buy on bid was pressed')).style('width:9em;align-items:center;text-align:center;')

with ui.expansion('orders', icon='work').classes('w-full'):
    log = ui.log(max_lines=10).classes('w-full h-16')
    ui.button('Log time', on_click=lambda: log.push('new order'))


## Update UI
# def update_elements():

# t = ui.timer(interval=0.01, callback=update_elements)

## Run
ui.run(title='Featuremine orders', reload=False, show=False)
