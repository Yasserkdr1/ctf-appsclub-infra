FROM ctfd/ctfd:3.8.9

USER root

COPY --chown=1001:1001 \
  plugins/ctfd_chall_manager/ \
  /opt/CTFd/CTFd/plugins/ctfd_chall_manager/

RUN chmod -R a+rX \
  /opt/CTFd/CTFd/plugins/ctfd_chall_manager

USER 1001

# AppsClub authenticated player VPN self-service plugin
COPY --chown=1001:1001 appsclub_vpn /opt/CTFd/CTFd/plugins/appsclub_vpn
