import { createRouter, createWebHistory } from "vue-router"
import ProjectHub from "./components/ProjectHub.vue"
import Cockpit from "./components/Cockpit.vue"

const routes = [
    {
        path: "/",
        name: "hub",
        component: ProjectHub
    },
    {
        path: "/project/:id",
        name: "cockpit",
        component: Cockpit,
        props: true
    },
    // Catch-all redirect to hub
    {
        path: "/:pathMatch(.*)*",
        redirect: "/"
    }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

export default router
