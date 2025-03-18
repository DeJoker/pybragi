

import logging
import subprocess


def port_to_docker_name(port: int, last_docker_id = ""):
    command = f"sudo netstat -tnlp |grep {port}" + " | awk '{print $7}' | cut -d'/' -f1"
    result = subprocess.run(command, shell=True, text=True, capture_output=True)
    stdout, stderr = result.stdout.strip(), result.stderr.strip()
    if result.returncode != 0:
        logging.info(f"{command} returncode:{result.returncode} {stdout}, {stderr}")
        return None
    pid = stdout
    command = f"sudo ps -eo pid,cgroup |grep {pid}" + " | grep -Po '(?:/docker/|docker-|docker\\.)\K\w+' | head -1"
    result = subprocess.run(command, shell=True, text=True, capture_output=True)
    stdout, stderr = result.stdout.strip(), result.stderr.strip()
    logging.info(f"{command} returncode:{result.returncode} {stdout}, {stderr}")
    if result.returncode != 0:
        return None
    pod_id = stdout

    # 通过docker ID获取docker名称
    command = f"sudo docker inspect --format='{{{{.Name}}}}' {pod_id} | sed 's/^\///' "
    result = subprocess.run(command, shell=True, text=True, capture_output=True)
    stdout, stderr = result.stdout.strip(), result.stderr.strip()
    logging.info(f"{command} returncode:{result.returncode} {stdout}, {stderr}")
    if result.returncode != 0:
        return None
    docker_name = stdout
    if last_docker_id != docker_name:
        logging.info(f"{port} docker_id is {docker_name}")
    return docker_name


def docker_kill(id_or_name: str):
    if not id_or_name:
        logging.info(f"no docker_id to kill {id_or_name}")
        return
    command = f"docker kill {id_or_name}; docker rm {id_or_name}"
    result = subprocess.run(command, shell=True, text=True, capture_output=True)
    stdout, stderr = result.stdout.strip(), result.stderr.strip()
    logging.info(f"{command} returncode:{result.returncode} {stdout}, {stderr}")
    return