"""Check the appended media record and clock evidence against frozen source hashes."""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import json

from check_coastal_day_followup import BASE, digest


DATA = BASE / '2026-11-21-video-clock'


def load(name):
    return json.loads((DATA / name).read_bytes())


def check_publications():
    clip = load('video-source.json')
    original = clip['officialPost']
    yle = clip['yleItem']
    assert original['url'] == yle['embedUrl']
    assert original['watchUrl'] == original['url'] + '/video/1'
    assert original['readableMediaVerified']
    for record, timestamp in [(original, '2026-11-21T19:03:09.000Z'),
                              (yle, '2026-11-21T19:31:39.791983Z')]:
        assert record['publishedAtUtc'] == timestamp
        local = datetime.fromisoformat(record['publishedAtEet'])
        assert local == datetime.fromisoformat(timestamp) and local.utcoffset() == timedelta(hours=2)
    video = clip['video']
    assert video['source']['status'] == 200 and video['source']['contentType'] == 'video/mp4'
    assert 9 < video['containerDurationSeconds'] < 10
    assert video['cameraTimeUtc'] is None and video['cameraOffset'] is None
    return clip


def check_camera(clip):
    camera = load('camera-clock-evidence.json')
    source = camera['sourcePhoto']
    photo = BASE / '2026-11-21-fire-evidence' / source['id']
    assert source['sha256'] == digest(photo) == clip['daylightStillClock']['source']['sha256']
    visible = camera['visibleOverlay']
    assert visible == {'label': '21/11/26 16:38:09:08', 'offset': None, 'finalFieldMeaning': None}
    tags = camera['jpegExif']['tags']
    assert tags['DateTimeOriginal'] == tags['DateTimeDigitized'] == '2026:11:21 15:48:16'
    assert tags['OffsetTime'] == tags['OffsetTimeOriginal'] == tags['OffsetTimeDigitized'] == '+02:00'
    photo_bytes = photo.read_bytes()
    assert all(value.encode('ascii') + b'\0' in photo_bytes for value in set(tags.values()))
    exif = datetime.strptime(tags['DateTimeOriginal'] + ' ' + tags['OffsetTimeOriginal'], '%Y:%m:%d %H:%M:%S %z')
    last_modified = parsedate_to_datetime(source['httpLastModified'])
    for row, offset_hours in zip(camera['interpretations'], (2, 0), strict=True):
        zone = timezone(timedelta(hours=offset_hours))
        stamp = datetime(2026, 11, 21, 16, 38, 9, tzinfo=zone)
        assert datetime.fromisoformat(row['wouldBeUtc']) == stamp
        assert datetime.fromisoformat(row['wouldBeEet']) == stamp
        assert row['secondsUntilHttpLastModified'] == (last_modified - stamp).total_seconds()
        assert row['secondsAfterJpegExifDateTimeOriginal'] == (stamp - exif).total_seconds()


def check_replay():
    replay = load('marinetraffic-record.json')
    assert replay['mediaId'] == 'C0D6suL7' and replay['durationSeconds'] == 50
    assert replay['exactSuppliedBlobMatched'] is False
    assert datetime.fromtimestamp(replay['playerPubdateUnixSeconds'], timezone.utc) == datetime.fromisoformat(replay['playerPubdateUtc'])
    assert len({record['labelAsPublished'] for record in replay['articleEmbeds']}) == 2


if __name__ == '__main__':
    manifest = load('sha256.json')
    assert set(manifest) == {p.name for p in DATA.iterdir() if p.name != 'sha256.json'}
    for name, sha in manifest.items():
        assert digest(DATA / name) == sha, name
    check_camera(check_publications())
    check_replay()
    print('Video and clock evidence verified: source publications, EXIF, overlay hypotheses and MarineTraffic metadata.')
