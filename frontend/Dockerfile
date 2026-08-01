FROM node:23 AS base

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable

WORKDIR /app

COPY package.json pnpm-workspace.yaml /app/
RUN pnpm install

COPY . /app/

# Accept build arguments and set as environment variables for Vite build
ARG GOOGLE_MAPS_API_KEY
ENV GOOGLE_MAPS_API_KEY=$GOOGLE_MAPS_API_KEY

ARG TOSS_CLIENT_KEY
ENV TOSS_CLIENT_KEY=$TOSS_CLIENT_KEY

ARG PAYPAL_CLIENT_ID
ENV PAYPAL_CLIENT_ID=$PAYPAL_CLIENT_ID

RUN pnpm run build

CMD ["bash", "run_server.sh"]