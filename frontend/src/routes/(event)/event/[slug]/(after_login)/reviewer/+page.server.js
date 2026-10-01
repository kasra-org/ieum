import { get, post } from '$lib/fetch';
import { redirect } from '@sveltejs/kit';
import { error } from '@sveltejs/kit';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent, params, cookies }) {
    let rtn = await parent();

    const get_data_or_500 = async (item) => {
        const response = await get(`api/event/${params.slug}/${item}`, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            throw error(500, "Internal Server Error");
        }
    }

    if (rtn.is_reviewer) {
        rtn.vote = await get_data_or_500('reviewer/vote');
        if (rtn.vote.voted_abstracts.length === 0) {
            let abstracts = await get_data_or_500('review/abstracts');
            rtn.abstracts = [];
            for (let abstract of abstracts) {
                rtn.abstracts.push( await get_data_or_500(`abstract/${abstract.id}`) );
            }
        }
    } else {
        return redirect(303, `/event/${params.slug}`);
    }

    return rtn;
}

/** @type {import('./$types').Actions} */
export const actions = {
    submit_votes: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        let data = {
            voted_abstracts: formdata.get('voted_abstracts').split(',').map(abstract_id => {
                return parseInt(abstract_id);
            })
        };
        const response = await post(`api/event/${params.slug}/reviewer/vote`, data, cookies);
        if (response.ok && response.status === 200) {
            return JSON.stringify(response.data);
        } else {
            error(response.status, response.data);
        }
        return;
    },
};