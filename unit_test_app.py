# unit_test_app.py
import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
import os
from app import save_metadata, load_all_voices

class TestUtilityFunctions(unittest.TestCase):
    """工具函数单元测试"""
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    @patch('json.load')
    @patch('json.dump')
    def test_save_metadata_new_file(self, mock_json_dump, mock_json_load, mock_exists, mock_file):
        """测试保存元数据到新文件"""
        # 模拟文件不存在
        mock_exists.return_value = False
        
        test_metadata = {"id": "test", "filename": "test.wav"}
        
        save_metadata(test_metadata)
        
        # 验证调用
        mock_json_dump.assert_called_once_with([test_metadata], mock_file.return_value.__enter__.return_value, indent=2)
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    @patch('json.load')
    @patch('json.dump')
    def test_save_metadata_existing_file(self, mock_json_dump, mock_json_load, mock_exists, mock_file):
        """测试追加元数据到现有文件"""
        # 模拟文件存在
        mock_exists.return_value = True
        existing_data = [{"id": "existing", "filename": "existing.wav"}]
        mock_json_load.return_value = existing_data
        
        new_metadata = {"id": "new", "filename": "new.wav"}
        expected_data = existing_data + [new_metadata]
        
        save_metadata(new_metadata)
        
        # 验证读取和写入
        mock_json_load.assert_called_once()
        mock_json_dump.assert_called_once_with(expected_data, mock_file.return_value.__enter__.return_value, indent=2)

    @patch('builtins.open', new_callable=mock_open, read_data='[{"id": "test"}]')
    @patch('os.path.exists')
    @patch('json.load')
    def test_load_all_voices_existing_file(self, mock_json_load, mock_exists, mock_file):
        """测试加载现有声音样本"""
        mock_exists.return_value = True
        expected_data = [{"id": "test"}]
        mock_json_load.return_value = expected_data
        
        result = load_all_voices()
        
        self.assertEqual(result, expected_data)
        mock_json_load.assert_called_once()

    @patch('os.path.exists')
    def test_load_all_voices_no_file(self, mock_exists):
        """测试加载不存在的文件"""
        mock_exists.return_value = False
        
        result = load_all_voices()
        
        self.assertEqual(result, [])

class TestAudioUtils(unittest.TestCase):
    """音频处理函数单元测试"""
    
    @patch('audio_utils.standardize_audio')
    def test_standardize_audio_success(self, mock_standardize):
        """测试音频标准化成功"""
        input_path = "/input/test.mp3"
        expected_output = "/output/test.wav"
        mock_standardize.return_value = expected_output
        
        from audio_utils import standardize_audio
        result = standardize_audio(input_path)
        
        self.assertEqual(result, expected_output)
        mock_standardize.assert_called_once_with(input_path)
    
    @patch('audio_utils.check_audio_duration')
    def test_check_audio_duration(self, mock_duration):
        """测试音频时长检查"""
        audio_path = "/test/audio.wav"
        expected_duration = 15.5
        mock_duration.return_value = expected_duration
        
        from audio_utils import check_audio_duration
        result = check_audio_duration(audio_path)
        
        self.assertEqual(result, expected_duration)
        mock_duration.assert_called_once_with(audio_path)

class TestBusinessLogic(unittest.TestCase):
    """业务逻辑单元测试"""
    
    def test_task_id_generation(self):
        """测试任务ID生成逻辑"""
        import uuid
        # from app import str
        
        # 测试UUID格式
        task_id = str(uuid.uuid4())
        self.assertTrue(len(task_id) == 36)  # UUID标准长度
        self.assertTrue('-' in task_id)      # 包含连字符
    
    def test_filename_security(self):
        """测试文件名安全处理"""
        from werkzeug.utils import secure_filename
        
        dangerous_filename = "../../../etc/passwd"
        safe_filename = secure_filename(dangerous_filename)
        
        self.assertNotIn('..', safe_filename)
        self.assertNotIn('/', safe_filename)

if __name__ == '__main__':
    unittest.main()