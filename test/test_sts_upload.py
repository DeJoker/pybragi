from io import BytesIO
import os
import requests
import tos # pip install tos


endpoint = "tos-cn-shanghai.volces.com"
external_endpoint = "tos-cn-shanghai.volces.com"
region = "cn-shanghai"
bucket = "rvc"

def upload_rvc_with_sts(bytes: BytesIO, request_id: str, ak: str, sk: str, stToken: str):
    client = tos.TosClientV2(ak, sk, external_endpoint, region, security_token=stToken)

    tos_path = f'audio/{request_id[:4]}/{request_id}.wav'
    try:
        resp = client.put_object(bucket, tos_path, content=bytes, 
                        content_type='audio/x-wav', forbid_overwrite=False
                    )
        print(f'success, resp:{vars(resp)}')
    except tos.exceptions.TosClientError as e:
        print(f'fail with client error, message:{e.message}, cause: {e.cause}')
    except Exception as e:
        print(f'fail with server error, code: {e}')
    return f"https://rvc.tos-cn-shanghai.volces.com/{tos_path}", resp.request_id != ""


if __name__ == '__main__':
    def test_sts():
        sts_resp = requests.get("http://14.103.229.186:50002/api/upload_sts").json()
        credential = sts_resp.get("credential", {})
        ak, sk, stToken = credential.get("AccessKeyId"), credential.get("SecretAccessKey"), credential.get("SessionToken")

        res = requests.get("http://zyvideo101.oss-cn-shanghai.aliyuncs.com/zyad/4e/33/1ce5-cd9e-11ef-bdec-00163e023ce8")
        res = upload_rvc_with_sts(BytesIO(res.content), 'c2', ak, sk, stToken)
        print(res)

    test_sts()

