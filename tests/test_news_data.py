import unittest
from unittest.mock import patch
from datetime import datetime,timezone
import news_data as news

class NewsTests(unittest.TestCase):
    def test_rss_plaintext_safe_links_publisher_and_tags(self):
        raw=b'''<rss><channel><item><title>XRP rises as analyst forecasts gains - Publisher</title><link>https://example.com/one</link><source>Publisher</source><pubDate>Wed, 14 Oct 2026 10:00:00 GMT</pubDate><description>&lt;b&gt;Ripple&lt;/b&gt; payment</description></item><item><title>bad</title><link>javascript:alert(1)</link></item></channel></rss>'''
        r=news.parse_feed(raw,'Google');self.assertEqual(len(r),1);self.assertEqual(r[0]['source'],'Publisher');self.assertNotIn(' - Publisher',r[0]['title']);self.assertEqual(r[0]['tone'],'positive');self.assertTrue(r[0]['analystCommentary']);self.assertNotIn('<b>',r[0]['snippet'])

    def test_atom_dates_and_xml_entity_rejection(self):
        raw=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Gold falls</title><link href="https://example.com/x"/><updated>2026-10-14T10:00:00Z</updated></entry></feed>'
        self.assertEqual(news.parse_feed(raw,'feed')[0]['publishedAt'],'2026-10-14T10:00:00+00:00')
        with self.assertRaises(ValueError):news.parse_feed(b'<!DOCTYPE rss [<!ENTITY a "XRP">]><rss/>','feed')

    def test_instrument_filters_and_lexical_tone_limits(self):
        self.assertFalse(news.matches('XLM','stellar earnings and stellar results'))
        self.assertTrue(news.matches('XLM','Stellar network blockchain upgrade'))
        self.assertFalse(news.matches('SILVER','a silver lining'))
        self.assertFalse(news.matches('GOLD','golden age'))
        self.assertTrue(news.matches('OIL','OPEC production and WTI'))
        self.assertEqual(news.headline_tags('XRP rises but falls later')['tone'],'mixed')

    def test_failure_retains_old_items_explicitly_and_caches_failure(self):
        old={'provider':'test','url':'https://example.com/rss','items':[{'title':'XRP'}],'attempt':0,'fetchedAt':'2026-01-01','error':None,'stale':False}
        with patch.dict(news.CACHE,{'https://example.com/rss':old},clear=True),patch('network_guard.read',side_effect=OSError()) as fetch:
            r=news.fetch_feed(('test','https://example.com/rss'));r2=news.fetch_feed(('test','https://example.com/rss'))
            self.assertTrue(r['stale']);self.assertIsNotNone(r['error']);self.assertEqual(r['items'],old['items']);self.assertEqual(r2,r);fetch.assert_called_once()

    def test_dedup_and_stale_or_undated_items_excluded_from_summary(self):
        item={'title':'XRP rises','snippet':'','url':'https://example.com/a','source':'test','feed':'test','publishedAt':datetime.now(timezone.utc).isoformat(),**news.headline_tags('XRP rises')}
        def feed(spec):return {'provider':spec[0],'url':spec[1],'items':[item,{**item,'title':'XRP falls','publishedAt':None}],'fetchedAt':item['publishedAt'],'stale':False,'error':None}
        with patch('news_data.fetch_feed',side_effect=feed):r=news.get_news('XRP')
        self.assertEqual(len(r['items']),2);self.assertEqual(r['summary']['recentCount'],1)
        with patch('news_data.fetch_feed',side_effect=lambda s:{**feed(s),'stale':True}):r=news.get_news('XRP')
        self.assertEqual(r['summary']['recentCount'],0)
