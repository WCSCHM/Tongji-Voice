import unittest
import json
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from io import BytesIO
from app import app, save_metadata, load_all_voices

class TestFlaskApp(unittest.TestCase):
    """Flask应用程序单元测试"""
    
    def setUp(self):
        """在每个测试前运行的设置"""
        # 创建临时测试目录
        self.test_dir = tempfile.mkdtemp()
        
        # 配置测试环境
        app.config['TESTING'] = True
        app.config['UPLOAD_FOLDER'] = os.path.join(self.test_dir, 'uploads')
        app.config['WTF_CSRF_ENABLED'] = False
        
        # 创建测试客户端
        self.client = app.test_client()
        
        # 确保测试目录存在
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'pptx'), exist_ok=True)
        
        # 更新全局路径配置
        import app as app_module
        app_module.UPLOAD_FOLDER = app.config['UPLOAD_FOLDER']
        app_module.PPT_FOLDER = os.path.join(app.config['UPLOAD_FOLDER'], 'pptx')
        app_module.METADATA_PATH = os.path.join(app.config['UPLOAD_FOLDER'], 'audio_metadata.json')
        app_module.TEXT_TASK_PATH = os.path.join(app.config['UPLOAD_FOLDER'], 'text_tasks.json')

    def tearDown(self):
        """在每个测试后运行的清理"""
        # 删除临时测试目录
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # 测试基础路由
    def test_welcome_page(self):
        """测试欢迎页面路由"""
        with patch('app.render_template') as mock_render:
            mock_render.return_value = '<html>欢迎页面</html>'
            response = self.client.get('/')
            self.assertEqual(response.status_code, 200)
            mock_render.assert_called_with('welcome.html')
        
    def test_main_page(self):
        """测试主页面路由"""
        with patch('app.render_template') as mock_render:
            mock_render.return_value = '<html>主页面</html>'
            response = self.client.get('/main')
            self.assertEqual(response.status_code, 200)
            mock_render.assert_called_with('index.html')

    # 测试声音样本相关接口
    def test_list_voices_empty(self):
        """测试获取空的声音样本列表"""
        response = self.client.get('/list_voices')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data, [])
    
    def test_list_voices_with_data(self):
        """测试获取有数据的声音样本列表"""
        # 先添加测试数据
        test_metadata = {
            "id": "test-voice-1",
            "filename": "test.wav",
            "duration": 10.5,
            "upload_time": "2025-01-01 12:00:00",
            "path": "/test/path/test.wav"
        }
        save_metadata(test_metadata)
        
        response = self.client.get('/list_voices')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['id'], 'test-voice-1')

    @patch('app.standardize_audio')
    @patch('app.check_audio_duration')
    def test_upload_audio_success(self, mock_check_duration, mock_standardize):
        """测试成功上传音频"""
        # 模拟音频处理函数
        mock_standardize.return_value = os.path.join(app.config['UPLOAD_FOLDER'], 'processed_test.wav')
        mock_check_duration.return_value = 15.0
        
        # 创建假的音频文件
        data = {
            'file': (BytesIO(b'fake audio data'), 'test.wav')
        }
        
        response = self.client.post('/upload_audio', data=data)
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.data)
        self.assertEqual(response_data['message'], '上传成功')
        self.assertIn('id', response_data)

    def test_upload_audio_no_file(self):
        """测试上传音频时没有文件"""
        response = self.client.post('/upload_audio', data={})
        self.assertEqual(response.status_code, 400)
        
        response_data = json.loads(response.data)
        self.assertEqual(response_data['error'], 'No file provided')

    @patch('app.standardize_audio')
    @patch('app.check_audio_duration')
    def test_upload_audio_processing_error(self, mock_check_duration, mock_standardize):
        """测试音频处理失败"""
        # 模拟处理异常
        mock_standardize.side_effect = Exception("音频处理失败")
        
        data = {
            'file': (BytesIO(b'fake audio data'), 'test.wav')
        }
        
        response = self.client.post('/upload_audio', data=data)
        self.assertEqual(response.status_code, 500)
        
        response_data = json.loads(response.data)
        self.assertEqual(response_data['error'], '音频处理失败')

    # 测试文本任务相关接口
    def test_submit_text_task_missing_params(self):
        """测试提交文本任务时缺少参数"""
        # 测试缺少text
        response = self.client.post('/submit_text_task', 
                                  json={'voice_id': 'test-id'})
        self.assertEqual(response.status_code, 400)
        
        # 测试缺少voice_id
        response = self.client.post('/submit_text_task', 
                                  json={'text': 'test text'})
        self.assertEqual(response.status_code, 400)

    def test_submit_text_task_invalid_text_length(self):
        """测试提交文本任务时文本长度不符合要求"""
        # 文本太短
        short_text = 'a' * 500
        response = self.client.post('/submit_text_task', 
                                  json={'text': short_text, 'voice_id': 'test-id'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('文本长度应在800到2000字符之间', 
                     json.loads(response.data)['error'])
        
        # 文本太长
        long_text = 'a' * 2500
        response = self.client.post('/submit_text_task', 
                                  json={'text': long_text, 'voice_id': 'test-id'})
        self.assertEqual(response.status_code, 400)

    def test_submit_text_task_invalid_voice_id(self):
        """测试提交文本任务时voice_id无效"""
        valid_text = 'a' * 1000  # 符合长度要求的文本
        response = self.client.post('/submit_text_task', 
                                  json={'text': valid_text, 'voice_id': 'invalid-id'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data)['error'], '无效的 voice_id')

    def test_submit_text_task_success(self):
        """测试成功提交文本任务"""
        # 先添加一个有效的voice
        test_metadata = {
            "id": "valid-voice-id",
            "filename": "test.wav",
            "duration": 10.5,
            "upload_time": "2025-01-01 12:00:00",
            "path": "/test/path/test.wav"
        }
        save_metadata(test_metadata)
        
        valid_text = 'a' * 1000  # 符合长度要求的文本
        response = self.client.post('/submit_text_task', 
                                  json={'text': valid_text, 'voice_id': 'valid-voice-id'})
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.data)
        self.assertEqual(response_data['message'], '文本任务已提交')
        self.assertIn('task_id', response_data)

    def test_list_text_tasks_empty(self):
        """测试获取空的任务列表"""
        response = self.client.get('/list_text_tasks')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data, [])

    def test_list_text_tasks_with_data(self):
        """测试获取有数据的任务列表"""
        # 先创建一个任务
        test_metadata = {
            "id": "valid-voice-id",
            "filename": "test.wav",
            "duration": 10.5,
            "upload_time": "2025-01-01 12:00:00",
            "path": "/test/path/test.wav"
        }
        save_metadata(test_metadata)
        
        valid_text = 'a' * 1000
        response = self.client.post('/submit_text_task', 
                                  json={'text': valid_text, 'voice_id': 'valid-voice-id'})
        task_id = json.loads(response.data)['task_id']
        
        # 获取任务列表
        response = self.client.get('/list_text_tasks')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['task_id'], task_id)

    # 测试音频生成和下载接口
    def test_generate_audio_missing_task_id(self):
        """测试生成音频时缺少task_id"""
        response = self.client.post('/generate_audio', json={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data)['error'], '缺少 task_id')

    def test_generate_audio_no_task_file(self):
        """测试生成音频时任务文件不存在"""
        response = self.client.post('/generate_audio', json={'task_id': 'test-id'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data)['error'], '任务列表为空')

    def test_generate_audio_task_not_found(self):
        """测试生成音频时找不到任务"""
        # 创建空的任务文件
        tasks_path = os.path.join(app.config['UPLOAD_FOLDER'], 'text_tasks.json')
        with open(tasks_path, 'w') as f:
            json.dump([], f)
        
        response = self.client.post('/generate_audio', json={'task_id': 'nonexistent-id'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(response.data)['error'], '未找到任务')

    @patch('app.pyttsx3')
    def test_generate_audio_success(self, mock_pyttsx3):
        """测试成功生成音频"""
        # 模拟pyttsx3
        mock_engine = MagicMock()
        mock_pyttsx3.init.return_value = mock_engine
        
        # 先创建一个任务
        test_metadata = {
            "id": "valid-voice-id",
            "filename": "test.wav",
            "duration": 10.5,
            "upload_time": "2025-01-01 12:00:00",
            "path": "/test/path/test.wav"
        }
        save_metadata(test_metadata)
        
        valid_text = 'a' * 1000
        response = self.client.post('/submit_text_task', 
                                  json={'text': valid_text, 'voice_id': 'valid-voice-id'})
        task_id = json.loads(response.data)['task_id']
        
        # 生成音频
        response = self.client.post('/generate_audio', json={'task_id': task_id})
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.data)
        self.assertEqual(response_data['message'], '音频生成成功')
        self.assertIn('audio_file', response_data)
        self.assertIn('download_url', response_data)

    def test_get_audio_no_task_file(self):
        """测试下载音频时任务文件不存在"""
        response = self.client.get('/get_audio/test-id')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(response.data)['error'], '任务记录不存在')

    def test_get_audio_task_not_found(self):
        """测试下载音频时找不到任务"""
        # 创建空的任务文件
        tasks_path = os.path.join(app.config['UPLOAD_FOLDER'], 'text_tasks.json')
        with open(tasks_path, 'w') as f:
            json.dump([], f)
        
        response = self.client.get('/get_audio/nonexistent-id')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(response.data)['error'], '任务未完成或未找到')

    def test_delete_task_no_file(self):
        """测试删除任务时文件不存在"""
        response = self.client.delete('/delete_task/test-id')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(response.data)['error'], '任务列表不存在')

    def test_delete_task_success(self):
        """测试成功删除任务"""
        # 先创建一个任务
        test_metadata = {
            "id": "valid-voice-id",
            "filename": "test.wav",
            "duration": 10.5,
            "upload_time": "2025-01-01 12:00:00",
            "path": "/test/path/test.wav"
        }
        save_metadata(test_metadata)
        
        valid_text = 'a' * 1000
        response = self.client.post('/submit_text_task', 
                                  json={'text': valid_text, 'voice_id': 'valid-voice-id'})
        task_id = json.loads(response.data)['task_id']
        
        # 删除任务
        response = self.client.delete(f'/delete_task/{task_id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data)['message'], f'任务 {task_id} 已删除')
        
        # 验证任务已被删除
        response = self.client.get('/list_text_tasks')
        data = json.loads(response.data)
        self.assertEqual(len(data), 0)

    # 测试PPT上传接口
    def test_upload_ppt_no_file(self):
        """测试上传PPT时没有文件"""
        response = self.client.post('/upload_ppt', data={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data)['error'], '没有上传文件')

    def test_upload_ppt_wrong_format(self):
        """测试上传非PPT文件"""
        data = {
            'file': (BytesIO(b'fake text data'), 'test.txt')
        }
        response = self.client.post('/upload_ppt', data=data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data)['error'], '只支持 .pptx 文件')

    @patch('app.Presentation')
    def test_upload_ppt_success(self, mock_presentation):
        """测试成功上传PPT"""
        # 模拟PPT解析
        mock_prs = MagicMock()
        mock_slide1 = MagicMock()
        mock_slide2 = MagicMock()
        
        # 模拟形状和文本
        mock_shape1 = MagicMock()
        mock_shape1.text = "第一页内容"
        mock_shape2 = MagicMock()
        mock_shape2.text = "第二页内容"
        
        mock_slide1.shapes = [mock_shape1]
        mock_slide2.shapes = [mock_shape2]
        mock_prs.slides = [mock_slide1, mock_slide2]
        
        mock_presentation.return_value = mock_prs
        
        # 上传PPT文件
        data = {
            'file': (BytesIO(b'fake pptx data'), 'test.pptx')
        }
        response = self.client.post('/upload_ppt', data=data)
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.data)
        self.assertIn('ppt_id', response_data)
        self.assertEqual(response_data['slide_count'], 2)
        self.assertEqual(len(response_data['slides']), 2)
        self.assertEqual(response_data['slides'][0], '第一页内容')
        self.assertEqual(response_data['slides'][1], '第二页内容')

    @patch('app.Presentation')
    def test_upload_ppt_parse_error(self, mock_presentation):
        """测试PPT解析失败"""
        # 模拟解析异常
        mock_presentation.side_effect = Exception("PPT文件损坏")
        
        data = {
            'file': (BytesIO(b'fake pptx data'), 'test.pptx')
        }
        response = self.client.post('/upload_ppt', data=data)
        self.assertEqual(response.status_code, 500)
        
        response_data = json.loads(response.data)
        self.assertIn('PPT解析失败', response_data['error'])


if __name__ == '__main__':
    unittest.main(verbosity=2)