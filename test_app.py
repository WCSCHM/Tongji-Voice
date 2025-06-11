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

    @patch('app.standardize_audio')
    @patch('app.check_audio_duration')
    def test_upload_audio_with_custom_id(self, mock_check_duration, mock_standardize):
        """测试使用自定义ID上传音频"""
        # 模拟音频处理函数
        mock_standardize.return_value = os.path.join(app.config['UPLOAD_FOLDER'], 'processed_test.wav')
        mock_check_duration.return_value = 15.0
        
        # 创建假的音频文件
        data = {
            'file': (BytesIO(b'fake audio data'), 'test.wav'),
            'custom_id': 'my-custom-voice-id'
        }
        
        response = self.client.post('/upload_audio', data=data)
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.data)
        self.assertEqual(response_data['message'], '上传成功')
        self.assertEqual(response_data['id'], 'my-custom-voice-id')

    @patch('app.standardize_audio')
    @patch('app.check_audio_duration')
    def test_upload_audio_duplicate_custom_id(self, mock_check_duration, mock_standardize):
        """测试上传重复自定义ID的音频"""
        # 先添加一个已存在的声音样本
        test_metadata = {
            "id": "existing-id",
            "filename": "test.wav",
            "duration": 10.5,
            "upload_time": "2025-01-01 12:00:00",
            "path": "/test/path/test.wav"
        }
        save_metadata(test_metadata)
        
        # 尝试使用相同ID上传
        data = {
            'file': (BytesIO(b'fake audio data'), 'test.wav'),
            'custom_id': 'existing-id'
        }
        
        response = self.client.post('/upload_audio', data=data)
        self.assertEqual(response.status_code, 400)
        
        response_data = json.loads(response.data)
        self.assertEqual(response_data['error'], '该声音样本ID已存在')

    def test_upload_audio_no_file(self):
        """测试上传音频时没有文件"""
        response = self.client.post('/upload_audio', data={})
        self.assertEqual(response.status_code, 400)
        
        response_data = json.loads(response.data)
        self.assertEqual(response_data['error'], 'No file provided')

    def test_upload_audio_empty_filename(self):
        """测试上传空文件名"""
        data = {
            'file': (BytesIO(b'fake audio data'), '')
        }
        response = self.client.post('/upload_audio', data=data)
        self.assertEqual(response.status_code, 400)
        
        response_data = json.loads(response.data)
        self.assertEqual(response_data['error'], 'Empty filename')

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
        self.assertEqual(json.loads(response.data)['error'], 'text 和 voice_id 不能为空')
        
        # 测试缺少voice_id
        response = self.client.post('/submit_text_task', 
                                  json={'text': 'test text'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data)['error'], 'text 和 voice_id 不能为空')

    def test_submit_text_task_empty_text(self):
        """测试提交空文本"""
        response = self.client.post('/submit_text_task', 
                                  json={'text': '', 'voice_id': 'test-id'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data)['error'], 'text 和 voice_id 不能为空')

    def test_submit_text_task_invalid_voice_id(self):
        """测试提交文本任务时voice_id无效"""
        response = self.client.post('/submit_text_task', 
                                  json={'text': 'valid text', 'voice_id': 'invalid-id'})
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
        
        response = self.client.post('/submit_text_task', 
                                  json={'text': '这是一个测试文本', 'voice_id': 'valid-voice-id'})
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.data)
        self.assertEqual(response_data['message'], '文本任务已提交')
        self.assertIn('task_id', response_data)

    def test_submit_text_task_with_custom_task_id(self):
        """测试使用自定义任务ID提交文本任务"""
        # 先添加一个有效的voice
        test_metadata = {
            "id": "valid-voice-id",
            "filename": "test.wav",
            "duration": 10.5,
            "upload_time": "2025-01-01 12:00:00",
            "path": "/test/path/test.wav"
        }
        save_metadata(test_metadata)
        
        response = self.client.post('/submit_text_task', 
                                  json={
                                      'text': '这是一个测试文本', 
                                      'voice_id': 'valid-voice-id',
                                      'custom_task_id': 'my-custom-task'
                                  })
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.data)
        self.assertEqual(response_data['message'], '文本任务已提交')
        self.assertEqual(response_data['task_id'], 'my-custom-task')

    def test_submit_text_task_duplicate_custom_task_id(self):
        """测试提交重复自定义任务ID"""
        # 先添加一个有效的voice
        test_metadata = {
            "id": "valid-voice-id",
            "filename": "test.wav",
            "duration": 10.5,
            "upload_time": "2025-01-01 12:00:00",
            "path": "/test/path/test.wav"
        }
        save_metadata(test_metadata)
        
        # 先创建一个任务
        self.client.post('/submit_text_task', 
                        json={
                            'text': '第一个任务', 
                            'voice_id': 'valid-voice-id',
                            'custom_task_id': 'existing-task'
                        })
        
        # 尝试使用相同ID创建另一个任务
        response = self.client.post('/submit_text_task', 
                                  json={
                                      'text': '第二个任务', 
                                      'voice_id': 'valid-voice-id',
                                      'custom_task_id': 'existing-task'
                                  })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data)['error'], '该任务ID已存在')

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
        
        response = self.client.post('/submit_text_task', 
                                  json={'text': '测试文本', 'voice_id': 'valid-voice-id'})
        task_id = json.loads(response.data)['task_id']
        
        # 获取任务列表
        response = self.client.get('/list_text_tasks')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['task_id'], task_id)
        self.assertEqual(data[0]['text'], '测试文本')
        self.assertEqual(data[0]['voice_id'], 'valid-voice-id')
        self.assertEqual(data[0]['status'], 'pending')

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

    def test_generate_audio_voice_sample_not_found(self):
        """测试生成音频时找不到声音样本"""
        # 创建一个任务但不创建对应的声音样本
        tasks_path = os.path.join(app.config['UPLOAD_FOLDER'], 'text_tasks.json')
        tasks = [{
            "task_id": "test-task",
            "voice_id": "nonexistent-voice",
            "text": "测试文本",
            "status": "pending"
        }]
        with open(tasks_path, 'w') as f:
            json.dump(tasks, f)
        
        response = self.client.post('/generate_audio', json={'task_id': 'test-task'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(response.data)['error'], '找不到声音样本')

    @patch('app.TTS_MODEL')
    def test_generate_audio_success(self, mock_tts_model):
        """测试成功生成音频"""
        # 模拟TTS模型
        mock_tts_model.tts_to_file = MagicMock()
        
        # 先创建一个声音样本
        test_metadata = {
            "id": "valid-voice-id",
            "filename": "test.wav",
            "duration": 10.5,
            "upload_time": "2025-01-01 12:00:00",
            "path": os.path.join(app.config['UPLOAD_FOLDER'], "test.wav")
        }
        save_metadata(test_metadata)
        
        # 创建实际的音频文件（用于检查存在性）
        with open(test_metadata["path"], 'w') as f:
            f.write("fake audio")
        
        # 创建一个任务
        response = self.client.post('/submit_text_task', 
                                  json={'text': '测试文本', 'voice_id': 'valid-voice-id'})
        task_id = json.loads(response.data)['task_id']
        
        # 生成音频
        response = self.client.post('/generate_audio', json={'task_id': task_id})
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.data)
        self.assertEqual(response_data['message'], '音频生成成功')
        self.assertIn('audio_file', response_data)
        self.assertIn('download_url', response_data)
        self.assertEqual(response_data['download_url'], f'/get_audio/{task_id}')
        
        # 验证TTS模型被调用
        mock_tts_model.tts_to_file.assert_called_once()

    @patch('app.TTS_MODEL')
    def test_generate_audio_tts_error(self, mock_tts_model):
        """测试TTS生成失败"""
        # 模拟TTS模型抛出异常
        mock_tts_model.tts_to_file.side_effect = Exception("TTS模型错误")
        
        # 先创建一个声音样本
        test_metadata = {
            "id": "valid-voice-id",
            "filename": "test.wav",
            "duration": 10.5,
            "upload_time": "2025-01-01 12:00:00",
            "path": os.path.join(app.config['UPLOAD_FOLDER'], "test.wav")
        }
        save_metadata(test_metadata)
        
        # 创建实际的音频文件
        with open(test_metadata["path"], 'w') as f:
            f.write("fake audio")
        
        # 创建一个任务
        response = self.client.post('/submit_text_task', 
                                  json={'text': '测试文本', 'voice_id': 'valid-voice-id'})
        task_id = json.loads(response.data)['task_id']
        
        # 生成音频
        response = self.client.post('/generate_audio', json={'task_id': task_id})
        self.assertEqual(response.status_code, 500)
        
        response_data = json.loads(response.data)
        self.assertIn('TTS 合成失败', response_data['error'])

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

    def test_get_audio_task_not_completed(self):
        """测试下载未完成任务的音频"""
        # 创建一个未完成的任务
        tasks_path = os.path.join(app.config['UPLOAD_FOLDER'], 'text_tasks.json')
        tasks = [{
            "task_id": "pending-task",
            "voice_id": "test-voice",
            "text": "测试文本",
            "status": "pending"
        }]
        with open(tasks_path, 'w') as f:
            json.dump(tasks, f)
        
        response = self.client.get('/get_audio/pending-task')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(response.data)['error'], '任务未完成或未找到')

    def test_get_audio_file_not_exist(self):
        """测试下载不存在的音频文件"""
        # 创建一个已完成但文件不存在的任务
        tasks_path = os.path.join(app.config['UPLOAD_FOLDER'], 'text_tasks.json')
        tasks = [{
            "task_id": "completed-task",
            "voice_id": "test-voice",
            "text": "测试文本",
            "status": "completed",
            "output_audio": "nonexistent.wav"
        }]
        with open(tasks_path, 'w') as f:
            json.dump(tasks, f)
        
        response = self.client.get('/get_audio/completed-task')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(response.data)['error'], '音频文件不存在')

    def test_get_audio_success(self):
        """测试成功下载音频"""
        # 创建一个已完成的任务和对应的音频文件
        audio_filename = "test_output.wav"
        audio_path = os.path.join(app.config['UPLOAD_FOLDER'], audio_filename)
        with open(audio_path, 'w') as f:
            f.write("fake audio content")
        
        tasks_path = os.path.join(app.config['UPLOAD_FOLDER'], 'text_tasks.json')
        tasks = [{
            "task_id": "completed-task",
            "voice_id": "test-voice",
            "text": "测试文本",
            "status": "completed",
            "output_audio": audio_filename
        }]
        with open(tasks_path, 'w') as f:
            json.dump(tasks, f)
        
        response = self.client.get('/get_audio/completed-task')
        self.assertEqual(response.status_code, 200)
        # 验证是否返回了文件内容
        self.assertEqual(response.data, b"fake audio content")

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
        
        response = self.client.post('/submit_text_task', 
                                  json={'text': '测试文本', 'voice_id': 'valid-voice-id'})
        task_id = json.loads(response.data)['task_id']
        
        # 删除任务
        response = self.client.delete(f'/delete_task/{task_id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data)['message'], f'任务 {task_id} 已删除')
        
        # 验证任务已被删除
        response = self.client.get('/list_text_tasks')
        data = json.loads(response.data)
        self.assertEqual(len(data), 0)

    def test_delete_task_with_audio_file(self):
        """测试删除带有音频文件的任务"""
        # 创建音频文件
        audio_filename = "test_output.wav"
        audio_path = os.path.join(app.config['UPLOAD_FOLDER'], audio_filename)
        with open(audio_path, 'w') as f:
            f.write("fake audio content")
        
        # 创建已完成的任务
        tasks_path = os.path.join(app.config['UPLOAD_FOLDER'], 'text_tasks.json')
        tasks = [{
            "task_id": "task-with-audio",
            "voice_id": "test-voice",
            "text": "测试文本",
            "status": "completed",
            "output_audio": audio_filename
        }]
        with open(tasks_path, 'w') as f:
            json.dump(tasks, f)
        
        # 验证音频文件存在
        self.assertTrue(os.path.exists(audio_path))
        
        # 删除任务
        response = self.client.delete('/delete_task/task-with-audio')
        self.assertEqual(response.status_code, 200)
        
        # 验证音频文件也被删除
        self.assertFalse(os.path.exists(audio_path))

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
    def test_upload_ppt_empty_slides(self, mock_presentation):
        """测试上传空内容的PPT"""
        # 模拟空的PPT
        mock_prs = MagicMock()
        mock_slide = MagicMock()
        mock_slide.shapes = []  # 空的形状列表
        mock_prs.slides = [mock_slide]
        
        mock_presentation.return_value = mock_prs
        
        data = {
            'file': (BytesIO(b'fake pptx data'), 'test.pptx')
        }
        response = self.client.post('/upload_ppt', data=data)
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.data)
        self.assertEqual(response_data['slide_count'], 1)
        self.assertEqual(response_data['slides'][0], '')  # 空内容

    @patch('app.Presentation')
    def test_upload_ppt_mixed_shapes(self, mock_presentation):
        """测试PPT包含有文本和无文本的形状"""
        # 模拟PPT解析
        mock_prs = MagicMock()
        mock_slide = MagicMock()
        
        # 创建不同类型的形状
        mock_text_shape = MagicMock()
        mock_text_shape.text = "有文本的形状"
        
        mock_no_text_shape = MagicMock()
        # 这个形状没有text属性，模拟图片等
        del mock_no_text_shape.text
        
        mock_slide.shapes = [mock_text_shape, mock_no_text_shape]
        mock_prs.slides = [mock_slide]
        
        mock_presentation.return_value = mock_prs
        
        data = {
            'file': (BytesIO(b'fake pptx data'), 'test.pptx')
        }
        response = self.client.post('/upload_ppt', data=data)
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.data)
        self.assertEqual(response_data['slide_count'], 1)
        self.assertEqual(response_data['slides'][0], '有文本的形状')

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

    # 测试工具函数
    def test_save_and_load_metadata(self):
        """测试元数据保存和加载功能"""
        # 测试保存第一个元数据
        metadata1 = {
            "id": "voice-1",
            "filename": "test1.wav",
            "duration": 10.5,
            "upload_time": "2025-01-01 12:00:00",
            "path": "/test/path1.wav"
        }
        save_metadata(metadata1)
        
        voices = load_all_voices()
        self.assertEqual(len(voices), 1)
        self.assertEqual(voices[0]['id'], 'voice-1')
        
        # 测试追加第二个元数据
        metadata2 = {
            "id": "voice-2",
            "filename": "test2.wav",
            "duration": 15.0,
            "upload_time": "2025-01-01 13:00:00",
            "path": "/test/path2.wav"
        }
        save_metadata(metadata2)
        
        voices = load_all_voices()
        self.assertEqual(len(voices), 2)
        self.assertEqual(voices[1]['id'], 'voice-2')

    def test_load_metadata_empty_file(self):
        """测试加载空的元数据文件"""
        voices = load_all_voices()
        self.assertEqual(voices, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)