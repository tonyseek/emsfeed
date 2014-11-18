from collections import namedtuple
from hashlib import sha1
from datetime import datetime

from click import command, option
from flask import Flask, g, render_template, request
from brownant import Dinergate
from brownant.pipeline.network import TextResponseProperty
from brownant.pipeline.html import ElementTreeProperty, XPathTextProperty
from werkzeug.contrib.atom import AtomFeed


app = Flask(__name__)


class Step(namedtuple('Step', 'date location milestone reason remark')):
    @property
    def title(self):
        return '{0} {1}'.format(self.date, self.milestone)

    @property
    def uuid(self):
        return sha1(self.title.encode('utf-8')).hexdigest()

    @property
    def author(self):
        return 'EMS'

    @property
    def updated(self):
        return datetime.strptime(self.date, '%Y-%m-%d %H:%M')


class TrackingInfo(Dinergate):
    URL_TEMPLATE = 'http://www.ems.com.cn/{self.channel}/query/{self.tid}'

    text_response = TextResponseProperty()
    etree = ElementTreeProperty()
    rows = XPathTextProperty(
        xpath='//*[@id="div1"]/table/tr[1]/td/table/tr', pick_mode='keep')

    def __init__(self, channel, tid):
        super().__init__(request=None, channel=channel, tid=tid)

    @property
    def title(self):
        return 'EMS - {0}:{1}'.format(self.channel.upper(), self.tid)

    @property
    def steps(self):
        rows = self.rows[2:]  # skip the table head
        steps = [[item.text for item in row] for row in rows if len(row) == 5]
        return [Step(*step) for step in steps]


@app.route('/')
def status():
    return render_template('status.txt'), 200, {'content-type': 'text/plain'}


@app.route('/feed')
def feed():
    dinergate = TrackingInfo(g.ems_channel, g.ems_tid)
    feed = AtomFeed(
        dinergate.title, feed_url=request.url, url=request.host_url)
    for step in dinergate.steps:
        content = render_template('step.txt', step=step)
        feed.add(
            step.title, content, content_type='text', author=step.author,
            url=dinergate.url, id=step.uuid, updated=step.updated,
            published=step.updated)
    return feed.get_response()


@app.before_request
def setup():
    g.ems_tid = app.config['EMS_TRACKING_ID']
    g.ems_channel = app.config['EMS_CHANNEL']


@command()
@option('--tracking-id', prompt='Tracking ID')
@option('--channel', default='apple')
@option('--debug', is_flag=True)
def main(tracking_id, channel, debug):
    app.config['DEBUG'] = debug
    app.config['EMS_TRACKING_ID'] = tracking_id
    app.config['EMS_CHANNEL'] = channel
    app.run()


if __name__ == '__main__':
    main()
