
```shell
export CUDA_VISIBLE_DEVICES="4";
conda activate ani;

curl localhost:8990/generate_by_img -d '{"img_file":"/aigc-nas01/cyj/draw_guess/service/clay_effect/tests/test_niantu.JPG"}'


curl http://60.217.224.164:50010/generate_by_img -d '{"prompt": "impasto,nijisusan, 1gril, masterpiece", "request_id":"31243jfiofjweoi"}'
```


