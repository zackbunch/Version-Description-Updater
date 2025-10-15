FROM fedora:latest

ARG username=ansible

USER root

RUN dnf update && \ 
    dnf install git zsh awk vim ssh python3 python3-pip just -y && \
    pip install ansible lxml ansible-lint --break-system-packages && \
    useradd ${username} && \
    echo "${username} ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

USER ${username}