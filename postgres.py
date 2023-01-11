#!/usr/bin/env python3
"""
/******************************************************************************

        COPYRIGHT (c) 2022 by Featuremine Corporation.
        This software has been provided pursuant to a License Agreement
        containing restrictions on its use.  This software contains
        valuable trade secrets and proprietary information of
        Featuremine Corporation and is protected by law.  It may not be
        copied or distributed in any form or medium, disclosed to third
        parties, reverse engineered or used in any manner not provided
        for in said License Agreement except with the prior written
        authorization from Featuremine Corporation.

 *****************************************************************************/
"""

"""
 * @file postgres.py
 * @date 20 Oct 2022
 * @brief Populate a PostgreSQL database with bars data from extractor
 */
"""
import argparse
import os
import functools
import extractor
from yamal import ytp
from conveyor.utils import schemas
import reference
from datetime import timedelta, datetime
import psycopg2
import time
from time import time_ns
import json
from common import StrategyOrderUpdater, OrderStateTable, OrderEventDetails, Side

# YTP channels prefix
prefix = "ore/imnts"

e2psqltype = {
    extractor.Time64: 'TIMESTAMP WITHOUT TIME ZONE',
    extractor.Rprice: 'NUMERIC NOT NULL',
    extractor.Float64: 'NUMERIC NOT NULL',
    extractor.Decimal128: 'NUMERIC NOT NULL',
    extractor.Int32: 'INT NOT NULL'
}

def extractor2psqlvalue(val):
    if isinstance(val, str):
        f"'{val}'"
    if isinstance(val, timedelta):
        return f"'{val + datetime(1970, 1, 1)}'"
    else:
        return str(val)

bars_descr = (("open_time", extractor.Time64),
                ("close_time", extractor.Time64),
                ("close_askpx", extractor.Decimal128),
                ("close_asksz", extractor.Decimal128),
                ("close_bidpx", extractor.Decimal128),
                ("close_bidsz", extractor.Decimal128),
                ("high_askpx", extractor.Decimal128),
                ("high_asksz", extractor.Decimal128),
                ("high_bidpx", extractor.Decimal128),
                ("high_bidsz", extractor.Decimal128),
                ("low_askpx", extractor.Decimal128),
                ("low_asksz", extractor.Decimal128),
                ("low_bidpx", extractor.Decimal128),
                ("low_bidsz", extractor.Decimal128),
                ("open_askpx", extractor.Decimal128),
                ("open_asksz", extractor.Decimal128),
                ("open_bidpx", extractor.Decimal128),
                ("open_bidsz", extractor.Decimal128),
                ("close_px", extractor.Decimal128),
                ("close_sz", extractor.Decimal128),
                ("high_px", extractor.Decimal128),
                ("high_sz", extractor.Decimal128),
                ("low_px", extractor.Decimal128),
                ("low_sz", extractor.Decimal128),
                ("open_px", extractor.Decimal128),
                ("open_sz", extractor.Decimal128),
                ("notional", extractor.Decimal128),
                ("vwap", extractor.Decimal128))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", help="postgreSQL database name", required=True)
    parser.add_argument("--user", help="postgreSQL user name", required=True)
    parser.add_argument("--password", help="postgreSQL database password", required=False, default="")
    parser.add_argument("--host", help="postgreSQL database host", required=False, default="127.0.0.1")
    parser.add_argument("--port", help="postgreSQL database port", required=False, default="5432")
    parser.add_argument("--peer", help="YTP peer reader", required=False, default="feed_handler")
    parser.add_argument("--markets", help="Comma separated markets list", required=True)
    parser.add_argument("--imnts", help="Comma separated instrument list", required=True)
    parser.add_argument("--period", help="Bar period in seconds", required=False, default=10)
    parser.add_argument("--levels", help="Book levels to display", required=False, default=1)
    parser.add_argument("--cfg", help="configuration file in JSON format", required=True, type=str)

    args = parser.parse_args()
    cfg = json.load(open(args.cfg))

    # Wait until the YTP file is created
    while not os.path.exists(cfg['price_ytp']):
        time.sleep(0.1)

    # Connect to PostgreSQL database
    tries = 10
    while True:
        try:
            conn = psycopg2.connect(database=args.database,
                                    user=args.user, password=args.password,
                                    host=args.host, port=args.port)
            break
        except psycopg2.OperationalError as e:
            if tries > 0:
                tries -= 1
            else:
                raise
        time.sleep(1)
    cur = conn.cursor()

    # Create database table to store market data
    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS market_data
    (
        bars_id SERIAL PRIMARY KEY NOT NULL,
        timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() at time zone 'utc'),
        market VARCHAR(32),
        imnt VARCHAR(32),
        {",".join([f'{field[0]} {e2psqltype[field[1]]}' for field in bars_descr])},
        UNIQUE (market, imnt, close_time)
    )
    """)
    conn.commit()

    # Venues and instruments
    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS venues
    (
        venueID INT PRIMARY KEY NOT NULL,
        name TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS imnts
    (
        imntID INT PRIMARY KEY NOT NULL,
        name TEXT NOT NULL
    );
    """)
    conn.commit()

    # Orders
    cur.execute(f"""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ordstatus') THEN
            create type ordstatus AS ENUM ('ack', 'unacked', 'done');
        END IF;
    END $$;
    CREATE TABLE IF NOT EXISTS orders
    (
        id INT NOT NULL,
        account TEXT NOT NULL,
        security TEXT NOT NULL,
        venue TEXT NOT NULL,
        strg TEXT NOT NULL,
        oms TEXT NOT NULL,
        side TEXT NOT NULL,
        price NUMERIC,
        quantity NUMERIC NOT NULL,
        done TEXT NOT NULL,
        PRIMARY KEY (strg, oms, id)
    );
    """)
    conn.commit()

    # Order Events
    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS order_events
    (
        pubseq INT PRIMARY KEY NOT NULL,
        type VARCHAR(12),
        id INT NOT NULL,
        account TEXT NOT NULL,
        security TEXT NOT NULL,
        venue TEXT NOT NULL,
        strg TEXT NOT NULL,
        oms TEXT NOT NULL,
        side TEXT NOT NULL,
        price NUMERIC,
        quantity NUMERIC,
        reason TEXT
    );
    """)
    conn.commit()

    bar_record_fields = [str(field[0]) for field in bars_descr]
    bar_records_str = ",".join(bar_record_fields)
    def bar2db(x, market, imnt):
        if x[0].vwap == extractor.Decimal128(0):
            return
        # Populate the market data parameters into the database
        values = ",".join([extractor2psqlvalue(getattr(x[0], f)) for f in bar_record_fields])
        cmd = f"""
        INSERT INTO market_data (market,imnt,{bar_records_str}) VALUES
        ('{market}','{imnt}',{values})
        ON CONFLICT  (market, imnt, close_time)
        DO UPDATE SET (market,imnt,{bar_records_str}) = ('{market}','{imnt}',{values});
        """
        cur.execute(cmd)
        conn.commit()

    def venues2db(delta):
        for id, venue in delta.venuesNames.items():
            print(id)
            print(venue)
            cmd = f"""
            INSERT INTO venues (venueID,name) VALUES
            ({id},'{venue.label}')
            ON CONFLICT (venueID)
            DO NOTHING
            """
            cur.execute(cmd)
            conn.commit()
        for id, security in delta.securities.items():
            print(id)
            print(security)
            cmd = f"""
            INSERT INTO imnts (imntID,name) VALUES
            ({id},'{security.symbol}')
            ON CONFLICT (imntID)
            DO NOTHING
            """
            cur.execute(cmd)
            conn.commit()

    orders = OrderStateTable()
    updater = StrategyOrderUpdater(orders)
    oe_details = OrderEventDetails()

    strg_pfx = f"{cfg['strategy_prefix']}"
    strg_pfx_len = len(strg_pfx) + 1
    trpseqno = 0
    def orders2db(peer, channel, time, data):
        global trpseqno
        trpseqno += 1
        msg = schemas.strategy.ManagerMessage.from_bytes_packed(data)
        first, _, second = channel.name()[strg_pfx_len:].partition('/')
        msgtype = msg.message.which()
        if msgtype == 'strg':
            strg = second
            oms = first
        else:
            strg = first
            oms = second
        ord = updater({
            "strg": strg,
            "oms": oms,
            "msg": msg
            })
        if ord is None:
            return

        ref = refdata.state
        dbid = ord.info['strgOrdID']
        dbacc = ord.info['accountID']
        dbsec = ref.securities[ord.info['securityId']].symbol.replace('-','_')
        dbven = ref.venuesNames[ord.info['venueID']].label
        dbside = 'buy' if ord.side == Side.BID else 'sell'
        dbpx = 'NULL' if ord.px is None else ord.px
        dbdone = 'done' if ord.done else 'active'
        cmd = f"""
        INSERT INTO orders (id,account,security,venue,strg,oms,side,price,quantity,done) VALUES
        ({dbid},'{dbacc}','{dbsec}','{dbven}','{strg}','{oms}','{dbside}',{dbpx},{ord.qty},'{dbdone}')
        ON CONFLICT
        DO NOTHING
        """
        cur.execute(cmd)
        conn.commit()
        
        tp, px, qt, reason = oe_details(msg)
        dbpx = 'NULL' if px is None else px
        dbqt = 'NULL' if qt is None else qt
        dbreason = 'NULL' if reason is None else reason
        cmd = f"""
        INSERT INTO order_events (pubseq,type,id,account,security,venue,strg,oms,side,price,quantity,reason) VALUES
        ({trpseqno},'{tp}',{dbid},'{dbacc}','{dbsec}','{dbven}','{strg}','{oms}','{dbside}',{dbpx},{dbqt},'{dbreason}')
        ON CONFLICT
        DO NOTHING
        """
        cur.execute(cmd)
        conn.commit()


    # TODO update to use ReferenceData and BarSignals

    graph = extractor.system.comp_graph()
    op = graph.features

    # Parse markets and instruments
    channels = []
    mktimnt = []
    for imnt in args.imnts.split(','):
        for mkt in args.markets.split(','):
            channels += [f"{prefix}/{mkt}/{imnt}"] # YTP channels for each market/instrument pair
            mktimnt += [(mkt,imnt)] # market/instrument pair

    def compute_bar(op, quote, trade, vendor_time):
        close_time = op.data_bar(vendor_time, timedelta(seconds=int(args.period)))
        open_time = op.tick_lag(close_time, 1)
        close_quote = op.left_lim(quote, close_time)
        open_quote = op.tick_lag(op.asof(quote, close_time), 1)

        high_quote = op.left_lim(op.asof(quote, op.max(quote.bidprice, close_time)), close_time)
        low_quote = op.left_lim(op.asof(quote, op.min(quote.askprice, close_time)), close_time)

        notional = op.left_lim(op.cumulative(trade.price * trade.qty), close_time)
        shares = op.left_lim(op.cumulative(trade.qty), close_time)
        prev_notional = op.tick_lag(notional, 1)
        prev_shares = op.tick_lag(shares, 1)
        notional = notional - prev_notional
        shares = shares - prev_shares

        first_trade = op.first_after(trade, close_time)
        open_trade_there = op.asof(first_trade, close_time)
        close_trade = op.asof(trade, close_time)
        no_trades = op.is_zero(shares)
        open_trade = op.cond(no_trades, close_trade, open_trade_there)

        high_trade_there = op.asof(op.asof(trade, op.max(trade.price, first_trade)), close_time)
        low_trade_there = op.asof(op.asof(trade, op.min(trade.price, first_trade)), close_time)

        high_trade = op.cond(no_trades, close_trade, high_trade_there)
        low_trade = op.cond(no_trades, close_trade, low_trade_there)

        # TODO: use mid price if no trade price exists yet
        vwap = op.cond(op.is_zero(shares), op.asof(trade.price, close_time), notional / shares)

        combined = op.combine(
            open_trade, (("price", "open_px"),
                        ("qty", "open_sz")),
            close_trade, (("price", "close_px"),
                        ("qty", "close_sz")),
            high_trade, (("price", "high_px"),
                        ("qty", "high_sz")),
            low_trade, (("price", "low_px"),
                        ("qty", "low_sz")),
            open_quote, (("bidprice", "open_bidpx"),
                        ("askprice", "open_askpx"),
                        ("bidqty", "open_bidsz"),
                        ("askqty", "open_asksz")),
            close_quote, (("bidprice", "close_bidpx"),
                        ("askprice", "close_askpx"),
                    ("bidqty", "close_bidsz"),
                        ("askqty", "close_asksz")),
            high_quote, (("bidprice", "high_bidpx"),
                        ("askprice", "high_askpx"),
                        ("bidqty", "high_bidsz"),
                        ("askqty", "high_asksz")),
            low_quote, (("bidprice", "low_bidpx"),
                        ("askprice", "low_askpx"),
                        ("bidqty", "low_bidsz"),
                        ("askqty", "low_asksz")),
            vwap, ("vwap",),
            notional, ("notional",),
            open_time, (("start", "open_time"),),
            close_time, (("start", "close_time"),),
            )
        
        # TODO: need to skip bars that have missing data
        return op.filter_unless(close_time.skipped, combined)

    def compute_bars(op, quotes, trades, times):
        return [compute_bar(op, quote, trd, ven) for quote, trd, ven, in zip(quotes, trades, times)]

    seq = ytp.sequence(cfg['price_ytp'])
    op.ytp_sequence(seq, timedelta(milliseconds=1))
    peer = seq.peer(args.peer)
    upds = [op.decode_data(op.ore_ytp_decode(peer.channel(time_ns(), ch))) for ch in channels]

    levels = [op.book_build(upd, args.levels) for upd in upds]
    times = [op.book_vendor_time(upd) for upd in upds]

    quotes = [op.combine(level,
                    (("bid_prx_0", "bidprice"),
                     ("bid_shr_0", "bidqty"),
                     ("ask_prx_0", "askprice"),
                     ("ask_shr_0", "askqty")))
            for level in levels]

    trades = [op.combine(op.book_trades(upd),
                        (("trade_price", "price"),
                         ("vendor", "receive"),
                         ("qty", "qty"),
                         ("decoration", "side")))
                for upd in upds]

    bars = compute_bars(op, quotes, trades, times)

    # Add a callback for each bar that corresponds to a market/instrument pair
    for bar, mi, trade in zip(bars, mktimnt, trades):
       graph.callback(bar, functools.partial(bar2db, market=mi[0], imnt=mi[1]))

    seqref = ytp.sequence(cfg['state_ytp'])
    refdata = reference.ReferenceData(seq=seqref, cfg=cfg)
    op.ytp_sequence(seqref, timedelta(milliseconds=1))
    refdata.add_callback(venues2db)
    refdata.poll()
    refdata.batch = False

    seqstrg = ytp.sequence(cfg['strategy_ytp'])
    seqstrg.data_callback(f"{strg_pfx}/", orders2db)
    op.ytp_sequence(seqstrg, timedelta(milliseconds=1))

    # Run the extractor blocking
    graph.stream_ctx().run_live()

    conn.close()
