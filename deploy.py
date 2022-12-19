import argparse
from reference import ReferenceBuilder
from yamal import ytp
import json

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--cfg", help="configuration file in JSON format", required=True, type=str)
    args = parser.parse_args()


    cfg = json.load(open(args.cfg))
    seq = ytp.sequence(cfg['state_ytp'])
    peer = seq.peer(cfg['peer'])

    ReferenceBuilder(peer, cfg)
