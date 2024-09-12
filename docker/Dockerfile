FROM alpine:3.20 AS builder

RUN adduser --disabled-password wirepas

# Install needed software
RUN apk add --no-cache gcc make musl-dev python3-dev py3-pip py3-wheel py3-setuptools rust cargo
RUN apk add --no-cache bash

# Copy provisioning server files
COPY --chown=wirepas . /home/wirepas/wm-provisioning
WORKDIR /home/wirepas/wm-provisioning

# Generate wheel
RUN rm -r build || true
RUN rm -r dist || true
RUN py3clean . || true
RUN python3 setup.py clean --all
RUN python3 setup.py sdist bdist_wheel

USER wirepas

# Install wheel
RUN pip3 install dist/wirepas_provisioning*.whl --user --break-system-packages

FROM alpine:3.20

RUN adduser --disabled-password wirepas

RUN apk add --no-cache python3 py3-six

USER wirepas
ENV PATH="/home/wirepas/.local/bin:${PATH}"

# Copy the built wheel and its dependencies from builder
COPY --from=builder /home/wirepas/.local /home/wirepas/.local

CMD ["wm-prov-srv"]