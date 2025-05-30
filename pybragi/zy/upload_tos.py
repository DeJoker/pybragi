from io import BytesIO
import os
import requests
import tos # pip install tos


from pybragi.base import time_utils

endpoint = "tos-cn-shanghai.volces.com"
external_endpoint = "tos-cn-shanghai.volces.com"
internal_endpoint = "tos-cn-shanghai.ivolces.com"
region = "cn-shanghai"
bucket = "rvc"

@time_utils.elapsed_time_limit(0.05)
def upload_rvc(bytes: BytesIO, request_id: str):
    client = tos.TosClientV2(os.getenv('TOS_ACCESS_KEY', ''), os.getenv('TOS_SECRET_KEY', ''), internal_endpoint, region)

    tos_path = f'audio/{request_id[-4:]}/{request_id}.wav'
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


@time_utils.elapsed_time_limit(0.05)
def upload_rvc_with_sts(bytes: BytesIO, request_id: str, ak: str, sk: str, stToken: str):
    client = tos.TosClientV2(ak, sk, external_endpoint, region, security_token=stToken)

    tos_path = f'audio/{request_id[-4:]}/{request_id}.wav'
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


def sts_creadent():
    # https://www.volcengine.com/docs/6349/127695
    from volcengine.sts.StsService import StsService

    stsService = StsService()
    stsService.set_ak(os.getenv('TOS_ACCESS_KEY'))
    stsService.set_sk(os.getenv('TOS_SECRET_KEY'))
    
    params = {
        "region": region,
        "DurationSeconds": "900",
        "RoleSessionName": "just_for_upload",
        "RoleTrn": "trn:iam::2102615123:role/tos-rvc"
    }

    res = stsService.assume_role(params)
    print(res)
    credential = res.get("Result", {}).get("Credentials", {})
    return credential




if __name__ == '__main__':
    def test_upload():
        res = requests.get("http://zyvideo101.oss-cn-shanghai.aliyuncs.com/zyad/4e/33/1ce5-cd9e-11ef-bdec-00163e023ce8")
        res = upload_rvc(BytesIO(res.content), 'c')
        print(res)
    
    def test_sts():
        credential = sts_creadent()
        ak, sk, stToken = credential.get("AccessKeyId"), credential.get("SecretAccessKey"), credential.get("SessionToken")

        res = requests.get("http://zyvideo101.oss-cn-shanghai.aliyuncs.com/zyad/4e/33/1ce5-cd9e-11ef-bdec-00163e023ce8")
        res = upload_rvc_with_sts(BytesIO(res.content), 'c2', ak, sk, stToken)
        print(res)

    test_sts()

