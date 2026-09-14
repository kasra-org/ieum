FROM node:23 AS base

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable

WORKDIR /app

# The lockfile has to come along: without it pnpm resolves the whole tree afresh
# on every build, so the image drifts from what was tested locally and a build
# can break with no change on our side. --frozen-lockfile then fails loudly if
# package.json and the lockfile ever disagree, rather than quietly re-resolving.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml /app/
RUN pnpm install --frozen-lockfile

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