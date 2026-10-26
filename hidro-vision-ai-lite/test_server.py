import http.client
import threading
import unittest
from http.server import ThreadingHTTPServer
from server import Handler


class QuietHandler(Handler):
    def log_message(self,*args):pass


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.server=ThreadingHTTPServer(('127.0.0.1',0),QuietHandler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(5)

    def request(self,method,path,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        conn.request(method,path,headers=headers or {})
        response=conn.getresponse();status=response.status;body=response.read();conn.close()
        return status,body

    def test_health_and_host_validation(self):
        self.assertEqual(self.request('GET','/api/health')[0],200)
        self.assertEqual(self.request('GET','/api/health',{'Host':'untrusted.invalid'})[0],403)
        self.assertEqual(self.request('POST','/api/platform/send-report',{'Host':'untrusted.invalid'})[0],403)

    def test_secrets_are_not_served_and_post_requires_local_header(self):
        self.assertEqual(self.request('GET','/integration_config.json')[0],404)
        self.assertEqual(self.request('POST','/api/platform/send-report')[0],403)
        self.assertEqual(self.request('POST','/api/platform/send-report',{'Origin':'https://untrusted.invalid','X-Hidro-Client':'local'})[0],403)


if __name__=='__main__':unittest.main()
