import unittest

from parser.preprocess import mask


class TestPreprocess(unittest.TestCase):
    def test_different_timestamps(self):
        text1 = "11:28:34.324 [XNIO-1 task-1]  X9DS5dE-TXas1V0YZg-nmg DEBUG c.n.openapi.ApiNormalisedPath <init> - normalised = /oauth2/client"
        text2 = "15:48:24.326 [XNIO-1 task-1]  X9DS5dE-TXas1V0YZg-nmg DEBUG c.n.openapi.ApiNormalisedPath <init> - normalised = /oauth2/client"

        masked_text1 = mask(text1)
        masked_text2 = mask(text2)

        self.assertEqual(masked_text1, masked_text2)

    def test_different_jsons(self):
        text1 = "11:28:34.847 [XNIO-1 task-1]  X9DS5dE-TXas1V0YZg-nmg DEBUG com.networknt.schema.TypeValidator debug - validate( {\"clientType\":\"public\",\"clientProfile\":\"mobile\",\"clientName\":\"YAz_a\",\"clientDesc\":\"DT8vLF_\",\"ownerId\":\"vhXiH54Jor\"}, {\"clientType\":\"public\",\"clientProfile\":\"mobile\",\"clientName\":\"YAz_a\",\"clientDesc\":\"DT8vLF_\",\"ownerId\":\"vhXiH54Jor\"}, requestBody)"
        text2 = "11:28:34.847 [XNIO-1 task-1]  X9DS5dE-TXas1V0YZg-nmg DEBUG com.networknt.schema.TypeValidator debug - validate( {\"clientSecret\":\"dyAj\",\"clientType\":\"public\",\"clientProfile\":\"mobile\",\"clientName\":\"YAz_a\",\"clientDesc\":\"DT8vLF_\",\"ownerId\":\"vhXiH54Jor\",\"host\":\"AHfcRBZC\",\"scope\":\"a59rtNNQD\",\"customClaim\":\"_9uGCM6_jbvAln\",\"redirectUri\":\"W5m\",\"derefClientId\":\"Zblf6tc8U_OfxKp\"}, {\"clientSecret\":\"dyAj\",\"clientType\":\"public\",\"clientProfile\":\"mobile\",\"clientName\":\"YAz_a\",\"clientDesc\":\"DT8vLF_\",\"ownerId\":\"vhXiH54Jor\",\"host\":\"AHfcRBZC\",\"scope\":\"a59rtNNQD\",\"customClaim\":\"_9uGCM6_jbvAln\",\"redirectUri\":\"W5m\",\"derefClientId\":\"Zblf6tc8U_OfxKp\"}, requestBody)"

        masked_text1 = mask(text1)
        masked_text2 = mask(text2)

        self.assertEqual(masked_text1, masked_text2)

    def test_log_level_concidered(self):
        text1 = "11:28:34.324 [XNIO-1 task-1]  X9DS5dE-TXas1V0YZg-nmg WARN c.n.openapi.ApiNormalisedPath <init> - normalised = /oauth2/client"
        text2 = "11:28:34.324 [XNIO-1 task-1]  X9DS5dE-TXas1V0YZg-nmg ERROR c.n.openapi.ApiNormalisedPath <init> - normalised = /oauth2/client"

        masked_text1 = mask(text1)
        masked_text2 = mask(text2)

        self.assertNotEqual(masked_text1, masked_text2)

    def test_non_ascii_text_survives(self):
        text1 = "11:28:34.324 [XNIO-1 task-1] INFO c.n.UserService create - Käyttäjä Märta lisätty 🎉 ユーザー登録完了 用户42"

        masked_text1 = mask(text1)

        self.assertIn("Käyttäjä Märta lisätty 🎉 ユーザー登録完了 用户", masked_text1)

    def test_different_messages_stay_different(self):
        text1 = "11:28:34.847 [XNIO-1 task-1]  X9DS5dE-TXas1V0YZg-nmg DEBUG com.networknt.schema.TypeValidator debug - validate( {\"clientType\":\"public\",\"clientProfile\":\"mobile\",\"clientName\":\"YAz_a\",\"clientDesc\":\"DT8vLF_\",\"ownerId\":\"vhXiH54Jor\"}, {\"clientType\":\"public\",\"clientProfile\":\"mobile\",\"clientName\":\"YAz_a\",\"clientDesc\":\"DT8vLF_\",\"ownerId\":\"vhXiH54Jor\"}, requestBody.clientType)"
        text2 = "11:28:34.847 [XNIO-1 task-1]  X9DS5dE-TXas1V0YZg-nmg DEBUG com.networknt.schema.TypeValidator debug - validate( {\"clientType\":\"public\",\"clientProfile\":\"mobile\",\"clientName\":\"YAz_a\",\"clientDesc\":\"DT8vLF_\",\"ownerId\":\"vhXiH54Jor\"}, {\"clientType\":\"public\",\"clientProfile\":\"mobile\",\"clientName\":\"YAz_a\",\"clientDesc\":\"DT8vLF_\",\"ownerId\":\"vhXiH54Jor\"}, requestBody.derefClientId)"

        masked_text1 = mask(text1)
        masked_text2 = mask(text2)

        self.assertNotEqual(masked_text1, masked_text2)
